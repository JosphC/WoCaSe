"""SQLite backend for the bench-data store.

Replaces the single-JSON-file approach with an SQLite database that provides:

  * **Selective reads/writes** — only the requested project is loaded, not
    the entire store.
  * **WAL mode** — multiple readers can query concurrently while a writer
    appends data (no more advisory lock files).
  * **SQL indexing** — project key look-ups are O(log n) via B-tree index.
  * **Built-in** — ``sqlite3`` ships with Python, zero extra dependencies.
  * **Atomic transactions** — ``BEGIN … COMMIT`` guarantees all-or-nothing
    writes; no more ``write-to-temp + os.replace`` needed.

Schema overview
---------------
::

    projects         — one row per project (key, full_name, metadata)
    bench_data       — normalised bench values (project_id × scenario × cal)
    config_params    — key/value pairs for ProjectConfig fields
    fitted_costs     — key/value pairs for MicroCosts fields
    calibrations     — (asyn, post) pairs per calibration index
    frf_blocks       — FrfBlock parameters per project

"""

from __future__ import annotations

import getpass
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from dem_simulator.config import ProjectConfig, FrfBlockConfig
from dem_simulator.costs import MicroCosts

logger = logging.getLogger("dem_simulator")

# ==============================================================================
#  Known config parameter types (module-level — allocated once)
# ==============================================================================

_FLOAT_PARAMS: frozenset = frozenset({"cpu_clock_mhz"})
_INT_PARAMS: frozenset = frozenset({
    "NrFmy", "NrFifoBas", "NrFifoIntm", "NrFifoRsv",
    "NrClcFmyEveAsyn", "NrClcFmyPost", "NrEve",
    "NrFrfDataTot", "NrFrfPreData", "NrBlockFrf", "NrFrfPre",
    "NrByteFrfFmy", "NrLamp", "NrFmyBufNvmWr", "NrClient",
})

# ==============================================================================
#  Schema
# ==============================================================================

_SCHEMA_VERSION = 1

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY,
    key         TEXT    UNIQUE NOT NULL,
    full_name   TEXT    DEFAULT '',
    uploaded_by TEXT    DEFAULT '',
    uploaded_at TEXT    DEFAULT '',
    fit_rmse    REAL    DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS bench_data (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scenario    TEXT    NOT NULL,
    cal_index   INTEGER NOT NULL,
    value_us    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (project_id, scenario, cal_index)
);

CREATE TABLE IF NOT EXISTS config_params (
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    param_name  TEXT    NOT NULL,
    param_value TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (project_id, param_name)
);

CREATE TABLE IF NOT EXISTS fitted_costs (
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    cost_name   TEXT    NOT NULL,
    cost_value  REAL    NOT NULL DEFAULT 0.0,
    PRIMARY KEY (project_id, cost_name)
);

CREATE TABLE IF NOT EXISTS calibrations (
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    cal_index   INTEGER NOT NULL,
    asyn        INTEGER NOT NULL DEFAULT 0,
    post        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (project_id, cal_index)
);

CREATE TABLE IF NOT EXISTS frf_blocks (
    id              INTEGER PRIMARY KEY,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    block_index     INTEGER NOT NULL,
    NrByteFrame     INTEGER DEFAULT 0,
    NrFrfIdxCalMax  INTEGER DEFAULT 0,
    NrIdxPerClass   INTEGER DEFAULT 0,
    NrFrfHold       INTEGER DEFAULT 0,
    NrFrfTot        INTEGER DEFAULT 0,
    LfOptions       INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_projects_key       ON projects(key);
CREATE INDEX IF NOT EXISTS idx_bench_project      ON bench_data(project_id);
CREATE INDEX IF NOT EXISTS idx_bench_proj_scn_cal ON bench_data(project_id, scenario, cal_index);
CREATE INDEX IF NOT EXISTS idx_config_project     ON config_params(project_id);
CREATE INDEX IF NOT EXISTS idx_costs_project      ON fitted_costs(project_id);
CREATE INDEX IF NOT EXISTS idx_cal_project        ON calibrations(project_id);
CREATE INDEX IF NOT EXISTS idx_frf_project        ON frf_blocks(project_id);
"""


# ==============================================================================
#  Connection helpers
# ==============================================================================

def _connect(db_path: str) -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure schema exists.

    Enables WAL mode for concurrent-read performance and foreign keys
    for referential integrity.
    """
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row  # access columns by name

    # PRAGMAs must be set outside transactions
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Use FULL synchronous on network shares to guarantee durability;
    # NORMAL can lose data when the filesystem doesn't honour fdatasync.
    _is_unc = db_path.startswith("\\\\") or db_path.startswith("//")
    conn.execute("PRAGMA synchronous=FULL" if _is_unc else "PRAGMA synchronous=NORMAL")

    # Create tables if first run — executescript() commits implicitly, which is
    # intentional here (schema setup is idempotent).
    conn.executescript(_SCHEMA_SQL)

    # Store schema version (outside executescript to use parameterised query)
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
        ("schema_version", str(_SCHEMA_VERSION)),
    )
    conn.commit()
    return conn


# ==============================================================================
#  Serialisation helpers (reused from bench_store.py concepts)
# ==============================================================================

def _normalise_key(project_name: str) -> str:
    """Normalise project name to upper-case, preserving the full name.

    Examples::

        "PROJ3_0U0_P16_624" → "PROJ3_0U0_P16_624"
        "  proj1  "          → "PROJ1"
        "FOH12_0U0"          → "FOH12_0U0"
    """
    return project_name.strip().upper()


# ==============================================================================
#  Internal write helpers
# ==============================================================================

def _upsert_project(
    conn: sqlite3.Connection,
    key: str,
    full_name: str = "",
    uploaded_by: str = "",
    uploaded_at: str = "",
    fit_rmse: float = 0.0,
) -> int:
    """Insert or update a project row.  Returns the project_id."""
    conn.execute(
        """INSERT INTO projects (key, full_name, uploaded_by, uploaded_at, fit_rmse)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET
               full_name   = excluded.full_name,
               uploaded_by = excluded.uploaded_by,
               uploaded_at = excluded.uploaded_at,
               fit_rmse    = excluded.fit_rmse
        """,
        (key, full_name, uploaded_by, uploaded_at, fit_rmse),
    )
    row = conn.execute(
        "SELECT id FROM projects WHERE key = ?", (key,)
    ).fetchone()
    return row["id"]


def _store_bench(
    conn: sqlite3.Connection,
    project_id: int,
    bench: Dict[str, List[int]],
) -> None:
    """Replace bench data for a project."""
    conn.execute("DELETE FROM bench_data WHERE project_id = ?", (project_id,))
    for scenario, values in bench.items():
        for cal_index, value in enumerate(values):
            conn.execute(
                "INSERT INTO bench_data (project_id, scenario, cal_index, value_us) "
                "VALUES (?, ?, ?, ?)",
                (project_id, scenario, cal_index, value),
            )


def _store_config(
    conn: sqlite3.Connection,
    project_id: int,
    cfg: ProjectConfig,
) -> None:
    """Replace config params for a project."""
    conn.execute("DELETE FROM config_params WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM frf_blocks WHERE project_id = ?", (project_id,))

    params = {
        "NrFmy": cfg.NrFmy,
        "NrFifoBas": cfg.NrFifoBas,
        "NrFifoIntm": cfg.NrFifoIntm,
        "NrFifoRsv": cfg.NrFifoRsv,
        "NrClcFmyEveAsyn": cfg.NrClcFmyEveAsyn,
        "NrClcFmyPost": cfg.NrClcFmyPost,
        "NrEve": cfg.NrEve,
        "NrFrfDataTot": cfg.NrFrfDataTot,
        "NrFrfPreData": cfg.NrFrfPreData,
        "NrBlockFrf": cfg.NrBlockFrf,
        "NrFrfPre": cfg.NrFrfPre,
        "NrByteFrfFmy": cfg.NrByteFrfFmy,
        "NrLamp": cfg.NrLamp,
        "NrFmyBufNvmWr": cfg.NrFmyBufNvmWr,
        "NrClient": cfg.NrClient,
        "cpu_clock_mhz": cfg.cpu_clock_mhz,
    }
    for name, value in params.items():
        conn.execute(
            "INSERT INTO config_params (project_id, param_name, param_value) "
            "VALUES (?, ?, ?)",
            (project_id, name, str(value)),
        )

    for idx, blk in enumerate(cfg.FrfBlocks):
        conn.execute(
            "INSERT INTO frf_blocks "
            "(project_id, block_index, NrByteFrame, NrFrfIdxCalMax, "
            " NrIdxPerClass, NrFrfHold, NrFrfTot, LfOptions) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, idx, blk.NrByteFrame, blk.NrFrfIdxCalMax,
             blk.NrIdxPerClass, blk.NrFrfHold, blk.NrFrfTot, blk.LfOptions),
        )


def _store_costs(
    conn: sqlite3.Connection,
    project_id: int,
    costs: MicroCosts,
) -> None:
    """Replace fitted costs for a project."""
    conn.execute("DELETE FROM fitted_costs WHERE project_id = ?", (project_id,))
    for name, value in costs.to_dict().items():
        conn.execute(
            "INSERT INTO fitted_costs (project_id, cost_name, cost_value) "
            "VALUES (?, ?, ?)",
            (project_id, name, value),
        )


def _store_calibrations(
    conn: sqlite3.Connection,
    project_id: int,
    calibrations: List[Tuple[int, int]],
) -> None:
    """Replace calibration pairs for a project."""
    conn.execute("DELETE FROM calibrations WHERE project_id = ?", (project_id,))
    for idx, (asyn, post) in enumerate(calibrations):
        conn.execute(
            "INSERT INTO calibrations (project_id, cal_index, asyn, post) "
            "VALUES (?, ?, ?, ?)",
            (project_id, idx, asyn, post),
        )


# ==============================================================================
#  Internal read helpers
# ==============================================================================

def _find_project_id(conn: sqlite3.Connection, project_name: str) -> Optional[int]:
    """Look up a project by name with cascading strategy.

    Search order:
      1. Exact match (full name, upper-cased).
      2. Prefix match — finds ``PROJ3_0U0_P16_624`` when searching ``PROJ3``.
         The underscore anchor (``PROJ3_%``) prevents ``PROJ3`` from matching
         ``PROJ30``, ``PROJ31``, etc.
    """
    key = project_name.strip().upper()
    # 1. Exact match
    row = conn.execute(
        "SELECT id FROM projects WHERE key = ?", (key,)
    ).fetchone()
    if row:
        return row["id"]
    # 2. Prefix match anchored at underscore to avoid partial-number collisions
    #    'PROJ3' matches 'PROJ3_0U0_...' but NOT 'PROJ30_...'
    matches = conn.execute(
        "SELECT id, key FROM projects WHERE key LIKE ? ORDER BY key",
        (key + "_%",),
    ).fetchall()
    if matches:
        if len(matches) > 1:
            matched_keys = [m["key"] for m in matches]
            logger.warning(
                "[BenchStoreDB] Prefix '%s' matched %d projects: %s "
                "— using first ('%s'). Consider using the full project key.",
                key, len(matches), matched_keys, matches[0]["key"],
            )
        return matches[0]["id"]
    return None


def _load_bench(
    conn: sqlite3.Connection,
    project_id: int,
) -> Dict[str, List[int]]:
    """Load bench data for a project, grouped by scenario.

    Values are placed at their stored ``cal_index`` position so that
    gaps (e.g. a missing calibration 2) result in a ``0`` at that slot
    rather than silently compacting the list.
    """
    rows = conn.execute(
        "SELECT scenario, cal_index, value_us FROM bench_data "
        "WHERE project_id = ? ORDER BY scenario, cal_index",
        (project_id,),
    ).fetchall()

    # First pass: determine the max cal_index per scenario
    max_idx: Dict[str, int] = {}
    for row in rows:
        scenario = row["scenario"]
        idx = row["cal_index"]
        if scenario not in max_idx or idx > max_idx[scenario]:
            max_idx[scenario] = idx

    # Second pass: allocate lists and place values at the right position
    result: Dict[str, List[int]] = {
        s: [0] * (mx + 1) for s, mx in max_idx.items()
    }
    for row in rows:
        result[row["scenario"]][row["cal_index"]] = row["value_us"]
    return result


def _load_config(
    conn: sqlite3.Connection,
    project_id: int,
    project_key: str,
) -> Optional[ProjectConfig]:
    """Load ProjectConfig from config_params + frf_blocks tables."""
    params = conn.execute(
        "SELECT param_name, param_value FROM config_params "
        "WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    if not params:
        return None

    d: Dict[str, Any] = {}
    for row in params:
        name = row["param_name"]
        val = row["param_value"]
        if name in _FLOAT_PARAMS:
            d[name] = float(val)
        elif name in _INT_PARAMS:
            # int("300.0") fails; go via float first, then round
            d[name] = int(round(float(val)))
        else:
            # Unknown param — best-effort numeric conversion
            try:
                d[name] = int(val)
            except ValueError:
                try:
                    d[name] = float(val)
                except ValueError:
                    d[name] = val

    blocks_rows = conn.execute(
        "SELECT * FROM frf_blocks WHERE project_id = ? ORDER BY block_index",
        (project_id,),
    ).fetchall()
    blocks = [
        FrfBlockConfig(
            NrByteFrame=r["NrByteFrame"],
            NrFrfIdxCalMax=r["NrFrfIdxCalMax"],
            NrIdxPerClass=r["NrIdxPerClass"],
            NrFrfHold=r["NrFrfHold"],
            NrFrfTot=r["NrFrfTot"],
            LfOptions=r["LfOptions"],
        )
        for r in blocks_rows
    ]

    try:
        return ProjectConfig(
            name=project_key,
            NrFmy=d.get("NrFmy", 0),
            NrFifoBas=d.get("NrFifoBas", 4),
            NrFifoIntm=d.get("NrFifoIntm", 8),
            NrFifoRsv=d.get("NrFifoRsv", 0),
            NrClcFmyEveAsyn=d.get("NrClcFmyEveAsyn", 20),
            NrClcFmyPost=d.get("NrClcFmyPost", 10),
            NrEve=d.get("NrEve", 0),
            NrFrfDataTot=d.get("NrFrfDataTot", 0),
            NrFrfPreData=d.get("NrFrfPreData", 0),
            NrBlockFrf=d.get("NrBlockFrf", 0),
            NrFrfPre=d.get("NrFrfPre", 0),
            NrByteFrfFmy=d.get("NrByteFrfFmy", 48),
            NrLamp=d.get("NrLamp", 0),
            NrFmyBufNvmWr=d.get("NrFmyBufNvmWr", 1),
            NrClient=d.get("NrClient", 6),
            cpu_clock_mhz=d.get("cpu_clock_mhz", 300.0),
            FrfBlocks=blocks,
        )
    except Exception as exc:
        logger.debug("[BenchStoreDB] Failed to build config for %s: %s",
                     project_key, exc)
        return None


def _load_costs(
    conn: sqlite3.Connection,
    project_id: int,
) -> Optional[MicroCosts]:
    """Load MicroCosts from fitted_costs table."""
    rows = conn.execute(
        "SELECT cost_name, cost_value FROM fitted_costs WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    if not rows:
        return None

    d = {row["cost_name"]: row["cost_value"] for row in rows}
    try:
        return MicroCosts.from_dict(d)
    except Exception as exc:
        logger.debug("[BenchStoreDB] Failed to build costs: %s", exc)
        return None


# ==============================================================================
#  Public API — Upload
# ==============================================================================

def upload_bench_result(
    db_path: str,
    project_name: str,
    bench: Dict[str, List[int]],
    cfg: Optional[ProjectConfig] = None,
    *,
    fitted_costs: Optional[MicroCosts] = None,
    fit_rmse: float = 0.0,
    calibrations: Optional[List[Tuple[int, int]]] = None,
    uploaded_by: str = "",
) -> str:
    """Upload bench results for a project to the SQLite store.

    Parameters mirror the JSON version in ``bench_store.py``.

    Returns the normalised project key.
    """
    key = _normalise_key(project_name)

    # Auto-fit if we have a config but no pre-fitted costs
    if fitted_costs is None and cfg is not None:
        try:
            from dem_simulator.transfer_fit import transfer_fit
            logger.info("[BenchStoreDB] Auto-fitting costs for %s ...", key)
            result = transfer_fit(cfg, bench)
            fitted_costs = result.costs
            fit_rmse = result.rmse_after
            logger.info(
                "[BenchStoreDB] Auto-fit complete: RMSE=%.2f us (%d iters)",
                result.rmse_after, result.iterations,
            )
        except Exception as exc:
            logger.warning(
                "[BenchStoreDB] Auto-fit failed for %s: %s", key, exc,
            )

    conn = _connect(db_path)
    try:
        with conn:
            project_id = _upsert_project(
                conn, key,
                full_name=project_name,
                uploaded_by=(
                    uploaded_by
                    or os.environ.get("USERNAME")
                    or os.environ.get("USER")
                    or getpass.getuser()
                ),
                uploaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                fit_rmse=round(fit_rmse, 3),
            )
            _store_bench(conn, project_id, bench)

            if cfg is not None:
                _store_config(conn, project_id, cfg)
            if fitted_costs is not None:
                _store_costs(conn, project_id, fitted_costs)
            if calibrations:
                _store_calibrations(conn, project_id, calibrations)

            # Update meta
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                ("last_updated", datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
        # Force WAL checkpoint so all data is flushed into the main .db file.
        # Without this, data stays in the -wal file and may not be visible
        # to other connections (especially on network shares).
        conn.execute("PRAGMA wal_checkpoint(FULL);")
    finally:
        conn.close()

    logger.info(
        "[BenchStoreDB] Uploaded %s to %s (fitted=%s, RMSE=%.2f)",
        key, db_path, fitted_costs is not None, fit_rmse,
    )
    return key


# ==============================================================================
#  Public API — Query
# ==============================================================================

def get_fitted_costs(
    db_path: str,
    project_name: str,
) -> Optional[MicroCosts]:
    """Retrieve pre-fitted MicroCosts for a project, or ``None``."""
    conn = _connect(db_path)
    try:
        pid = _find_project_id(conn, project_name)
        if pid is None:
            return None
        costs = _load_costs(conn, pid)
        if costs is not None:
            row = conn.execute(
                "SELECT fit_rmse FROM projects WHERE id = ?", (pid,)
            ).fetchone()
            logger.info(
                "[BenchStoreDB] Loaded fitted costs for %s (RMSE=%.2f us)",
                project_name, row["fit_rmse"] if row else 0,
            )
        return costs
    finally:
        conn.close()


def get_bench_data(
    db_path: str,
    project_name: str,
) -> Optional[Dict[str, List[int]]]:
    """Retrieve raw bench data for a project, or ``None``."""
    conn = _connect(db_path)
    try:
        pid = _find_project_id(conn, project_name)
        if pid is None:
            return None
        bench = _load_bench(conn, pid)
        return bench if bench else None
    finally:
        conn.close()


def get_all_configs(db_path: str) -> Dict[str, ProjectConfig]:
    """Return all stored ProjectConfigs (for enriching transfer-learning)."""
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT id, key FROM projects").fetchall()
        result: Dict[str, ProjectConfig] = {}
        for row in rows:
            cfg = _load_config(conn, row["id"], row["key"])
            if cfg is not None:
                result[row["key"]] = cfg
        return result
    finally:
        conn.close()


def get_all_fitted_costs(db_path: str) -> Dict[str, MicroCosts]:
    """Return all stored fitted costs (for enriching transfer-learning)."""
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT id, key FROM projects").fetchall()
        result: Dict[str, MicroCosts] = {}
        for row in rows:
            costs = _load_costs(conn, row["id"])
            if costs is not None:
                result[row["key"]] = costs
        return result
    finally:
        conn.close()


def list_projects(db_path: str) -> List[Dict[str, Any]]:
    """Return a summary list of all projects in the store."""
    conn = _connect(db_path)
    try:
        # Single query with LEFT JOIN aggregation — no N+1 problem.
        # Note: bench_data has an `id` column; fitted_costs uses (project_id,
        # cost_name) as PK, so we aggregate on project_id instead.
        rows = conn.execute("""
            SELECT
                p.id,
                p.key,
                p.uploaded_by,
                p.uploaded_at,
                p.fit_rmse,
                MAX(CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END) AS has_bench,
                MAX(CASE WHEN f.project_id IS NOT NULL THEN 1 ELSE 0 END) AS has_costs
            FROM projects p
            LEFT JOIN bench_data  b ON b.project_id = p.id
            LEFT JOIN fitted_costs f ON f.project_id = p.id
            GROUP BY p.id
            ORDER BY p.key
        """).fetchall()
        return [
            {
                "key":         row["key"],
                "has_bench":   bool(row["has_bench"]),
                "has_costs":   bool(row["has_costs"]),
                # use `is not None` so that a genuine 0.0 RMSE is kept as 0.0
                "fit_rmse":    row["fit_rmse"] if row["fit_rmse"] is not None else None,
                "uploaded_by": row["uploaded_by"],
                "uploaded_at": row["uploaded_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def delete_project(db_path: str, project_name: str) -> bool:
    """Delete a project and all its related data. Returns True if found."""
    conn = _connect(db_path)
    try:
        pid = _find_project_id(conn, project_name)
        if pid is None:
            return False
        with conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
        return True
    finally:
        conn.close()




def project_count(db_path: str) -> int:
    """Return the number of projects in the store."""
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM projects").fetchone()
        return row["cnt"]
    finally:
        conn.close()


def _clear_all_data(db_path: str) -> None:
    """INTERNAL: Delete all data from all tables (schema stays intact)."""
    conn = _connect(db_path)
    try:
        # Delete in reverse foreign-key dependency order
        conn.execute("DELETE FROM frf_blocks")
        conn.execute("DELETE FROM calibrations")
        conn.execute("DELETE FROM fitted_costs")
        conn.execute("DELETE FROM config_params")
        conn.execute("DELETE FROM bench_data")
        conn.execute("DELETE FROM projects")
        conn.commit()
    finally:
        conn.close()
