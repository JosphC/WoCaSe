"""
TD5 Build System Integration Module

Handles interaction with TD5 tool build system (import, build).
"""

import logging
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Tuple, List, Dict

from .logging_config import get_logger

logger = get_logger(__name__)
_td5_log = logging.getLogger("wcs.td5")


# ---------------------------------------------------------------------------
#  Lightweight data container
# ---------------------------------------------------------------------------

class TargetEntry:
    """A visible target extracted from a .tdxml file, with its build types."""

    __slots__ = ("name", "buildtypes")

    def __init__(self, name: str, buildtypes: List[str]):
        self.name = name
        self.buildtypes = buildtypes

    def __repr__(self) -> str:
        return f"TargetEntry({self.name!r}, {self.buildtypes!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TargetEntry):
            return NotImplemented
        return self.name == other.name and self.buildtypes == other.buildtypes


# ---------------------------------------------------------------------------
#  Low-level XML helpers
# ---------------------------------------------------------------------------

def _local_name(tag: str) -> str:
    """Strip XML namespace prefix and return the local tag name."""
    return tag.split('}')[-1]


def _parse_bool(text: Optional[str]) -> Optional[bool]:
    """Strict bool parse: 'true'/'false' (case-insensitive) -> True/False; else None."""
    if text is None:
        return None
    t = text.strip().lower()
    if t == 'true':
        return True
    if t == 'false':
        return False
    return None


def _collect_buildtypenames_from_element(element: ET.Element) -> List[str]:
    """Extract unique BuildTypeName values from a single XML subtree.

    Walks *element* looking for ``BuildProcessDefinition/BuildTypes/BuildType/
    BuildTypeName``.  Used both for per-target extraction (when *element* is a
    ``<TargetInformation>``) and for global extraction (when *element* is the
    document root).

    Returns:
        Ordered, deduplicated list of build-type name strings.
    """
    results: List[str] = []
    for bpd in element.iter():
        if _local_name(bpd.tag) != 'BuildProcessDefinition':
            continue
        for bt_container in bpd.iter():
            if _local_name(bt_container.tag) != 'BuildTypes':
                continue
            for bt in bt_container:
                if _local_name(bt.tag) != 'BuildType':
                    continue
                for child in bt:
                    if _local_name(child.tag) == 'BuildTypeName' and child.text:
                        name = child.text.strip()
                        if name:
                            results.append(name)
    # Deduplicate preserving order
    seen: set = set()
    uniq: List[str] = []
    for x in results:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


# ---------------------------------------------------------------------------
#  Multi-target / multi-buildtype extraction
# ---------------------------------------------------------------------------

def _collect_valid_target_names(root: ET.Element) -> List[str]:
    """Return TargetName values where IsInvisible is False or absent.

    Iterates every ``<TargetInformation>`` in the tree.  An entry is accepted
    when ``IsInvisible`` is **False** or the element is missing entirely.
    Entries with ``IsInvisible == True`` are silently skipped.

    Args:
        root: Root element of a parsed .tdxml file.

    Returns:
        Ordered list of valid target name strings (may be empty).
    """
    return [t.name for t in _collect_targets_with_buildtypes(root)]


def _collect_buildtypenames(root: ET.Element) -> List[str]:
    """Return unique BuildTypeName values from the entire tree.

    This is the *global* variant that merges build types across all targets.
    Kept for backward compatibility with tests and simpler call sites.
    """
    return _collect_buildtypenames_from_element(root)


def _collect_targets_with_buildtypes(root: ET.Element) -> List[TargetEntry]:
    """Return visible targets, each paired with its own build-type list.

    Iterates every ``<TargetInformation>`` block.  For each block that passes
    the visibility filter (``IsInvisible`` absent or ``false``), build types
    are resolved in two steps:

    1. Look for ``<BuildProcessDefinition>`` **inside** the
       ``<TargetInformation>`` element (some schemas nest it).
    2. If none are found there, fall back to the root-level
       ``<BuildProcessDefinition>`` which is a **sibling** of
       ``<TargetInformation>`` — this is the layout used by real TD5
       ``.tdxml`` files where each file represents one target.

    Args:
        root: Root element of a parsed ``.tdxml`` file.

    Returns:
        Ordered list of :class:`TargetEntry` instances (may be empty).
    """
    # Pre-compute root-level build types once (sibling layout)
    root_bts: Optional[List[str]] = None

    entries: List[TargetEntry] = []
    for ti in root.iter():
        if _local_name(ti.tag) != 'TargetInformation':
            continue

        # --- target name ---
        target_name: Optional[str] = None
        for e in ti.iter():
            if _local_name(e.tag) == 'TargetName' and e.text is not None:
                tn = e.text.strip()
                if tn:
                    target_name = tn

        # --- visibility ---
        is_invisible: Optional[bool] = None
        for e in ti.iter():
            if _local_name(e.tag).lower() == 'isinvisible':
                is_invisible = _parse_bool(e.text)

        if not target_name or is_invisible is True:
            continue

        # --- per-target build types (nested inside TargetInformation) ---
        bts = _collect_buildtypenames_from_element(ti)

        # --- fallback: root-level sibling BuildProcessDefinition ---
        if not bts:
            if root_bts is None:
                root_bts = _collect_buildtypenames_from_element(root)
            bts = list(root_bts)        # copy so each entry is independent

        entries.append(TargetEntry(target_name, bts))

    return entries


# ---------------------------------------------------------------------------
#  File / directory level API
# ---------------------------------------------------------------------------

def extract_targets_and_buildtypes_from_file(
    path: str,
) -> Tuple[List[str], List[str]]:
    """Parse a single .tdxml and return (target_names, global_buildtype_names).

    This is the *flat* API retained for backward compatibility.  For the
    per-target mapping use :func:`extract_targets_from_file` instead.
    """
    tree = ET.parse(path)
    root = tree.getroot()
    return _collect_valid_target_names(root), _collect_buildtypenames(root)


def extract_targets_from_file(path: str) -> List[TargetEntry]:
    """Parse a single .tdxml and return a list of :class:`TargetEntry`."""
    tree = ET.parse(path)
    return _collect_targets_with_buildtypes(tree.getroot())


def extract_from_dir(root_dir: str) -> Dict[str, Dict[str, List[str]]]:
    """Scan *root_dir* recursively for .tdxml files — flat API.

    Returns:
        ``{ path: {"targets": [...], "buildtypes": [...]} }``

        Only files that contain at least one valid TargetName are included.
    """
    result: Dict[str, Dict[str, List[str]]] = {}
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if not fn.lower().endswith('.tdxml'):
                continue
            p = str(Path(dirpath) / fn)
            try:
                targets, bts = extract_targets_and_buildtypes_from_file(p)
                if targets:
                    result[p] = {"targets": targets, "buildtypes": bts}
            except (ET.ParseError, OSError):
                continue
    return result


def extract_targets_from_dir(root_dir: str) -> Dict[str, List[TargetEntry]]:
    """Scan *root_dir* recursively — per-target API.

    Returns:
        ``{ path: [TargetEntry, ...] }``

        Only files that contain at least one valid target are included.
    """
    result: Dict[str, List[TargetEntry]] = {}
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            if not fn.lower().endswith('.tdxml'):
                continue
            p = str(Path(dirpath) / fn)
            try:
                entries = extract_targets_from_file(p)
                if entries:
                    result[p] = entries
            except (ET.ParseError, OSError):
                continue
    return result


# ---------------------------------------------------------------------------
#  High-level finders (used by main.py and the UI)
# ---------------------------------------------------------------------------

def find_target_name_recursively(root_dir: str) -> Optional[str]:
    """Return the best visible TargetName from .tdxml files under *root_dir*.

    Selection rules:
      - If only one file has valid targets: use its first target.
      - If multiple files: prefer shallowest, then newest mtime, then
        lexicographic path.

    Returns:
        Best target name, or ``None``.
    """
    root = Path(root_dir)
    if not root.exists():
        return None

    info = extract_from_dir(root_dir)
    if not info:
        return None

    if len(info) == 1:
        targets = next(iter(info.values()))["targets"]
        return targets[0] if targets else None

    def _rank(item: Tuple[str, dict]) -> tuple:
        p = Path(item[0])
        depth = len(p.relative_to(root).parts)
        mtime = p.stat().st_mtime if p.exists() else 0.0
        return (depth, -mtime, item[0].lower())

    ranked = sorted(info.items(), key=_rank)
    targets = ranked[0][1]["targets"]
    return targets[0] if targets else None


def find_buildtypes_recursively(root_dir: str) -> List[str]:
    """Return all unique BuildTypeName values under *root_dir*.

    Falls back to ``["NORMAL"]`` if nothing is found.
    """
    info = extract_from_dir(root_dir)
    seen: set = set()
    result: List[str] = []
    for entry in info.values():
        for bt in entry["buildtypes"]:
            if bt not in seen:
                seen.add(bt)
                result.append(bt)
    return result if result else ["NORMAL"]


def find_targets_recursively(root_dir: str) -> List[TargetEntry]:
    """Return all visible targets (with per-target build types) under *root_dir*.

    Merges results from every ``.tdxml`` found recursively.  Targets with
    identical names across different files are **deduplicated** — the first
    occurrence (shallowest file, newest mtime) wins.

    Falls back to an empty list when the directory does not exist or contains
    no ``.tdxml`` files with visible targets.

    Returns:
        Ordered list of :class:`TargetEntry` instances.
    """
    root = Path(root_dir)
    if not root.exists():
        return []

    file_map = extract_targets_from_dir(root_dir)
    if not file_map:
        return []

    # Sort files: shallowest first, newest mtime, then lexicographic
    def _file_rank(item: Tuple[str, List[TargetEntry]]) -> tuple:
        p = Path(item[0])
        depth = len(p.relative_to(root).parts)
        mtime = p.stat().st_mtime if p.exists() else 0.0
        return (depth, -mtime, item[0].lower())

    sorted_files = sorted(file_map.items(), key=_file_rank)

    seen_names: set = set()
    result: List[TargetEntry] = []
    for _, entries in sorted_files:
        for te in entries:
            if te.name not in seen_names:
                seen_names.add(te.name)
                result.append(te)
    return result


def _td5_env(td5_path: str) -> dict:
    """Build a clean environment for TD5 sub-processes.

    TD5 sets ``PYTHON_TD5_EXE`` / ``PYTHON_TD5_PATH`` internally for its
    own child processes, but when we launch ``td5.exe`` via CLI those
    variables are only visible *inside* the TD5 JVM — not in the
    environment that TD5 inherits from us.

    Meanwhile our process may be running inside an activated Python
    virtual-environment whose PATH no longer contains a system-level
    ``python``.  TD5 custom build steps (e.g. ``COPY_MANDATORY_LOGS``)
    call bare ``python`` and fail with *CreateProcess error=2*.

    This helper performs three sanitisation steps before prepending the
    TD5 bundled Python:

    1. **Remove ``VIRTUAL_ENV``** from the child environment entirely so
       that TD5's JVM does not propagate it to its own sub-processes.
    2. **Strip all PATH entries** that live under the venv root (not only
       the ``Scripts`` sub-directory), preventing any venv executable
       from shadowing system tools.
    3. **Clear ``PYTHONHOME``, ``PYTHONPATH`` and conda variables** that
       an active environment may have set and that override the bare
       ``python`` lookup.

    Args:
        td5_path: Absolute path to the ``td5.exe`` executable.

    Returns:
        A copy of ``os.environ`` with a repaired PATH and no venv/conda
        influence.
    """
    env = os.environ.copy()
    path_parts = env.get("PATH", "").split(os.pathsep)

    # --- Remove all virtual-env / conda influence ----------------------
    # Pop VIRTUAL_ENV entirely so TD5's JVM does not propagate it to the
    # custom build steps (e.g. COPY_MANDATORY_LOGS) that call bare 'python'.
    venv = env.pop("VIRTUAL_ENV", "")
    if venv:
        venv_lower = venv.lower()
        # Strip every PATH entry under the venv root, not just Scripts.
        path_parts = [p for p in path_parts
                      if not p.lower().startswith(venv_lower)]

    # Clear Python-level variables that a venv or conda activation sets
    # and that would redirect bare 'python' to the wrong interpreter.
    for _var in ("PYTHONHOME", "PYTHONPATH",
                 "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "_CONDA_EXE"):
        env.pop(_var, None)

    # --- Derive TD5 bundled Python dir ----------------------------------
    #  td5_path is typically:
    #    C:\LegacyApp\TD5\4.4.0\eclipse_cli\td5.exe
    #  TD5 root:
    #    C:\LegacyApp\TD5\4.4.0
    #  Bundled Python lives under:
    #    <root>\tools\python   or   <root>\python
    td5_exe = Path(td5_path).resolve()
    td5_root = td5_exe.parent.parent          # eclipse_cli -> <root>

    python_added = False
    for subdir in ("tools/python", "python", "tools/Python311",
                   "tools/Python310", "tools/Python39"):
        candidate = td5_root / subdir
        if (candidate / "python.exe").is_file():
            path_parts.insert(0, str(candidate))
            logger.debug("[TD5] Prepended TD5 Python to PATH: %s", candidate)
            python_added = True
            break

    # --- Fallback: scan common system-level installs --------------------
    if not python_added:
        for sysdir in (r"C:\LegacyApp\Python311",
                       r"C:\LegacyApp\python\3.10.0",
                       r"C:\Python311", r"C:\Python310", r"C:\Python39"):
            if os.path.isfile(os.path.join(sysdir, "python.exe")):
                path_parts.insert(0, sysdir)
                logger.debug("[TD5] Prepended system Python to PATH: %s", sysdir)
                python_added = True
                break

    if not python_added:
        logger.warning(
            "[TD5] Could not locate a system python.exe — TD5 custom "
            "processes that invoke 'python' may fail."
        )

    env["PATH"] = os.pathsep.join(path_parts)
    return env


def _no_console_kwargs() -> dict:
    """Windows: start subprocess without showing a console window."""
    if os.name != "nt":
        return {}
    
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    return {
        "startupinfo": si,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def importmks(td5_path: str, release_name: str) -> None:
    """
    Imports project from MKS using TD5.
    
    Args:
        td5_path: Path to TD5 executable
        release_name: Release name to import
    """
    logger.info("== Importing the project with TD5 ==")
    importmks_cmd = [
        td5_path,
        "importmks",
        f"-rn=FS_{release_name}",
        f"-n={release_name}",
        f"-mksbl=FS_{release_name}"
    ]
    logger.info("Running: %s", ' '.join(importmks_cmd))
    logger.info("[TD5] Starting importmks...")
    
    # Merge stderr into stdout so a full stderr buffer cannot deadlock
    # the process while we are reading stdout line-by-line.
    process = subprocess.Popen(
        importmks_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=_td5_env(td5_path),  #can be deleted 
        **_no_console_kwargs()
    )
    
    # Stream combined output in real-time
    for line in process.stdout:
        _td5_log.info(line.rstrip())
    
    process.wait()

    if process.returncode != 0:
        raise RuntimeError(f"[TD5 ERROR] Import mks failed with code {process.returncode}!")
    else:
        logger.info("[TD5] Import finished successfully!")


def importfs(td5_path: str, win_path: str, base_folder: str) -> None:
    """
    Imports project from file system using TD5.
    
    Args:
        td5_path: Path to TD5 executable
        win_path: Windows path to the project
        base_folder: Base folder name for the project
    """
    logger.info("== Importing the project with TD5 ==")
    import_cmd = [
        td5_path,
        "importfs",
        f"-rn=FS_{base_folder}",
        f"-i={win_path}"
    ]
    logger.info("Running: %s", ' '.join(import_cmd))
    logger.info("[TD5] Starting importfs...")
    
    # Merge stderr into stdout so a full stderr buffer cannot deadlock
    # the process while we are reading stdout line-by-line.
    process = subprocess.Popen(
        import_cmd,
        cwd=win_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=_td5_env(td5_path), #can be deleted 
        **_no_console_kwargs()
    )
    
    # Stream combined output in real-time
    for line in process.stdout:
        _td5_log.info(line.rstrip())
    
    process.wait()
    
    if process.returncode != 0:
        raise RuntimeError(f"[TD5 ERROR] Import failed with code {process.returncode}!")
    else:
        logger.info("[TD5] Import finished successfully!")


def buildprj(td5_path: str, proj_name: str, target_name: str, build_type: str, rule: str) -> None:
    """
    Builds the project using TD5.
    
    Args:
        td5_path: Path to TD5 executable
        proj_name: Project name
        target_name: Target name for the build
        build_type: Build type (e.g., "NORMAL")
        rule: Build rule (e.g., "All")
    """
    logger.info("== Building the project with TD5 ==")
    build_cmd = [
        td5_path,
        "buildprj",
        f"-n={proj_name}",
        f"-t={target_name}",
        f"-y={build_type}",
        f"-r={rule}",
        "-cb"
    ]
    logger.info("Running: %s", ' '.join(build_cmd))
    logger.info("[TD5] Starting build process...")

    # Merge stderr into stdout so a full stderr buffer cannot deadlock
    # the process while we are reading stdout line-by-line.
    process = subprocess.Popen(
        build_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=_td5_env(td5_path),  # can be deleted 
        **_no_console_kwargs()
    )
    
    # Stream combined output in real-time
    for line in process.stdout:
        _td5_log.info(line.rstrip())
    
    process.wait()
    
    if process.returncode != 0:
        raise RuntimeError(f"[TD5 ERROR] Build failed with code {process.returncode}!")
    else:
        logger.info("[TD5] Build finished successfully!")
