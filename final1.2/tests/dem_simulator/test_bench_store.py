"""Unit tests for dem_simulator.bench_store — SQLite backend.

Uses a temporary SQLite database to avoid polluting the real bench_store.db.

Covers:
  - Upload and query round-trip (SQLite)
  - Key normalisation (_normalise_key)
  - _key_variants lookup cascade
  - get_all_configs / get_all_fitted_costs
  - list_projects
  - Empty store returns None / empty
  - _parse_cell_int and _parse_asyn_post helpers
  - SQLite-specific features (delete_project, project_count)
"""

import os
import sqlite3
import tempfile
import unittest

from dem_simulator.config import ProjectConfig, FrfBlockConfig
from dem_simulator.costs import MicroCosts
from dem_simulator.bench_store import (
    upload_bench_result,
    get_fitted_costs,
    get_bench_data,
    get_all_configs,
    get_all_fitted_costs,
    list_projects,
    _normalise_key,
    _key_variants,
    _parse_cell_int,
    _parse_asyn_post,
)
from dem_simulator.bench_store_db import (
    delete_project,
    project_count,
)


def _make_cfg(name="TESTPROJ") -> ProjectConfig:
    return ProjectConfig(
        name=name, NrFmy=10, NrFifoBas=4, NrFifoIntm=8, NrFifoRsv=0,
        NrClcFmyEveAsyn=20, NrClcFmyPost=10, NrEve=100,
        NrFrfDataTot=40, NrFrfPreData=0, NrBlockFrf=1, NrFrfPre=4,
        NrByteFrfFmy=48, NrLamp=2, cpu_clock_mhz=300.0,
        FrfBlocks=[FrfBlockConfig(48, 6, 6, 2, 8, 0)],
    )


_BENCH = {
    "scenario_1": [400, 300, 250, 200, 180, 170],
    "scenario_2": [250, 200, 160, 130, 120, 110],
    "scenario_3": [410, 310, 260, 210, 190, 175],
}


class TestNormaliseKey(unittest.TestCase):
    """_normalise_key preserves full name, upper-cased."""

    def test_full_name_preserved(self):
        self.assertEqual(_normalise_key("PROJ3_0U0_P16_624"), "PROJ3_0U0_P16_624")

    def test_short_name(self):
        self.assertEqual(_normalise_key("PROJ2"), "PROJ2")

    def test_lowercase(self):
        self.assertEqual(_normalise_key("proj1"), "PROJ1")

    def test_whitespace(self):
        self.assertEqual(_normalise_key("  PROJ3  "), "PROJ3")

    def test_distinct_projects_have_distinct_keys(self):
        """Two projects sharing a prefix must NOT collide."""
        k1 = _normalise_key("ABC_123")
        k2 = _normalise_key("ABC_456")
        self.assertNotEqual(k1, k2)


class TestKeyVariants(unittest.TestCase):
    """_key_variants generates lookup cascade."""

    def test_short_name(self):
        variants = _key_variants("PROJ2")
        self.assertIn("PROJ2", variants)

    def test_long_name(self):
        variants = _key_variants("PROJ3_0U0_P16_624")
        self.assertIn("PROJ3_0U0_P16_624", variants)
        self.assertIn("PROJ3", variants)
        self.assertIn("PROJ3", variants)

    def test_no_duplicates(self):
        variants = _key_variants("PROJ")
        self.assertEqual(len(variants), len(set(variants)))


class TestParseCellInt(unittest.TestCase):
    """_parse_cell_int handles various Excel cell formats."""

    def test_int(self):
        self.assertEqual(_parse_cell_int(42), 42)

    def test_float(self):
        self.assertEqual(_parse_cell_int(42.7), 43)

    def test_string(self):
        self.assertEqual(_parse_cell_int("123"), 123)

    def test_string_with_unit(self):
        self.assertEqual(_parse_cell_int("450 us"), 450)

    def test_none(self):
        self.assertEqual(_parse_cell_int(None), 0)

    def test_empty_string(self):
        self.assertEqual(_parse_cell_int(""), 0)

    def test_blank_whitespace(self):
        """Whitespace-only cells return 0."""
        self.assertEqual(_parse_cell_int("   "), 0)
        self.assertEqual(_parse_cell_int("\xa0"), 0)

    def test_min_max_slash(self):
        """Two measurements separated by slash → average (regression for
        ALC34_0U0_201 bench cells like ``'596/594'`` which were being
        parsed as 596594 — catastrophic 1000x error)."""
        self.assertEqual(_parse_cell_int("596/594"), 595)
        self.assertEqual(_parse_cell_int("658/659"), 658)  # 658.5 banker's round
        self.assertEqual(_parse_cell_int("596 / 594"), 595)

    def test_min_max_dash(self):
        """Range notation ``'595-600'`` → average."""
        self.assertEqual(_parse_cell_int("595-600"), 598)  # 597.5 banker's round

    def test_value_with_nbsp(self):
        """Non-breaking space stripped correctly."""
        self.assertEqual(_parse_cell_int("498\xa0"), 498)

    def test_no_digits(self):
        """No digits in string → 0."""
        self.assertEqual(_parse_cell_int("n/a"), 0)
        self.assertEqual(_parse_cell_int("--"), 0)


class TestParseAsynPost(unittest.TestCase):
    """_parse_asyn_post parses calibration cell."""

    def test_slash_format(self):
        self.assertEqual(_parse_asyn_post("20/10"), (20, 10))

    def test_multiline(self):
        self.assertEqual(_parse_asyn_post("20/\n10\n"), (20, 10))

    def test_single_number(self):
        self.assertEqual(_parse_asyn_post("5"), (5, 5))

    def test_no_numbers(self):
        self.assertEqual(_parse_asyn_post("abc"), (0, 0))


class TestUploadAndQuery(unittest.TestCase):
    """Upload → query round-trip with temporary store file."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._store = os.path.join(self._tmpdir, "test_store.db")

    def tearDown(self):
        # Remove all files (db, wal, shm, lock)
        for f in os.listdir(self._tmpdir):
            os.remove(os.path.join(self._tmpdir, f))
        os.rmdir(self._tmpdir)

    def test_upload_creates_file(self):
        upload_bench_result(
            "TEST_PROJECT", _BENCH,
            fitted_costs=MicroCosts(),
            fit_rmse=5.0,
            store_path=self._store,
        )
        self.assertTrue(os.path.isfile(self._store))

    def test_query_returns_uploaded_costs(self):
        costs = MicroCosts(t_main_fixed=99.0)
        upload_bench_result(
            "MYPROJ", _BENCH,
            fitted_costs=costs,
            fit_rmse=3.0,
            store_path=self._store,
        )
        retrieved = get_fitted_costs("MYPROJ", store_path=self._store)
        self.assertIsNotNone(retrieved)
        self.assertAlmostEqual(retrieved.t_main_fixed, 99.0)

    def test_query_bench_data(self):
        upload_bench_result(
            "BENCHPROJ", _BENCH,
            store_path=self._store,
        )
        data = get_bench_data("BENCHPROJ", store_path=self._store)
        self.assertIsNotNone(data)
        self.assertEqual(data["scenario_1"], _BENCH["scenario_1"])

    def test_query_nonexistent_returns_none(self):
        result = get_fitted_costs("NONEXISTENT", store_path=self._store)
        self.assertIsNone(result)

    def test_get_all_configs(self):
        cfg = _make_cfg("CFGTEST")
        upload_bench_result(
            "CFGTEST", _BENCH,
            cfg=cfg,
            fitted_costs=MicroCosts(),
            store_path=self._store,
        )
        configs = get_all_configs(store_path=self._store)
        self.assertIn("CFGTEST", configs)  # normalised key = first token

    def test_get_all_fitted_costs(self):
        upload_bench_result(
            "FITTEST", _BENCH,
            fitted_costs=MicroCosts(t_lamp=7.7),
            store_path=self._store,
        )
        all_costs = get_all_fitted_costs(store_path=self._store)
        self.assertIn("FITTEST", all_costs)  # normalised = FITTEST (no underscore)

    def test_list_projects(self):
        upload_bench_result(
            "PROJ_A", _BENCH,
            fitted_costs=MicroCosts(),
            store_path=self._store,
        )
        upload_bench_result(
            "PROJ_B", _BENCH,
            store_path=self._store,
        )
        projects = list_projects(store_path=self._store)
        keys = [p["key"] for p in projects]
        self.assertIn("PROJ_A", keys)  # each project has its own key
        self.assertIn("PROJ_B", keys)
        self.assertEqual(sum(1 for key in keys if key in {"PROJ_A", "PROJ_B"}), 2)

    def test_prefix_lookup(self):
        """Query by short prefix finds entry stored under full key."""
        upload_bench_result(
            "XYZ_0U0_001", _BENCH,
            fitted_costs=MicroCosts(t_main_fixed=42.0),
            store_path=self._store,
        )
        # Exact match
        result = get_fitted_costs("XYZ_0U0_001", store_path=self._store)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.t_main_fixed, 42.0)
        # Prefix match
        result2 = get_fitted_costs("XYZ", store_path=self._store)
        self.assertIsNotNone(result2)
        self.assertAlmostEqual(result2.t_main_fixed, 42.0)

    def test_distinct_projects_not_overwritten(self):
        """Two projects with the same prefix must coexist."""
        upload_bench_result(
            "ABC_123", _BENCH,
            fitted_costs=MicroCosts(t_main_fixed=11.0),
            store_path=self._store,
        )
        upload_bench_result(
            "ABC_456", _BENCH,
            fitted_costs=MicroCosts(t_main_fixed=22.0),
            store_path=self._store,
        )
        c1 = get_fitted_costs("ABC_123", store_path=self._store)
        c2 = get_fitted_costs("ABC_456", store_path=self._store)
        self.assertIsNotNone(c1)
        self.assertIsNotNone(c2)
        self.assertAlmostEqual(c1.t_main_fixed, 11.0)
        self.assertAlmostEqual(c2.t_main_fixed, 22.0)


class TestSQLiteSpecific(unittest.TestCase):
    """SQLite-specific features."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._store = os.path.join(self._tmpdir, "sqlite_test.db")

    def tearDown(self):
        for f in os.listdir(self._tmpdir):
            os.remove(os.path.join(self._tmpdir, f))
        os.rmdir(self._tmpdir)

    def test_project_count(self):
        self.assertEqual(project_count(self._store), 0)
        upload_bench_result(
            "AAA", _BENCH,
            fitted_costs=MicroCosts(),
            store_path=self._store,
        )
        self.assertEqual(project_count(self._store), 1)

    def test_delete_project(self):
        upload_bench_result(
            "DELME", _BENCH,
            fitted_costs=MicroCosts(),
            store_path=self._store,
        )
        self.assertEqual(project_count(self._store), 1)
        deleted = delete_project(self._store, "DELME")
        self.assertTrue(deleted)
        self.assertEqual(project_count(self._store), 0)

    def test_delete_nonexistent(self):
        deleted = delete_project(self._store, "NOEXIST")
        self.assertFalse(deleted)

    def test_db_is_valid_sqlite(self):
        upload_bench_result(
            "VALID", _BENCH,
            store_path=self._store,
        )
        conn = sqlite3.connect(self._store)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        for expected in ["projects", "bench_data", "config_params",
                         "fitted_costs", "calibrations", "frf_blocks"]:
            self.assertIn(expected, table_names)
        conn.close()

    def test_wal_mode_enabled(self):
        upload_bench_result(
            "WAL", _BENCH,
            store_path=self._store,
        )
        conn = sqlite3.connect(self._store)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode, "wal")
        conn.close()

    def test_config_round_trip(self):
        """Config stored in SQLite reconstructs correctly."""
        cfg = _make_cfg("ROUNDTRIP_001")
        upload_bench_result(
            "ROUNDTRIP_001", _BENCH,
            cfg=cfg,
            fitted_costs=MicroCosts(),
            store_path=self._store,
        )
        configs = get_all_configs(store_path=self._store)
        self.assertIn("ROUNDTRIP_001", configs)
        restored = configs["ROUNDTRIP_001"]
        self.assertEqual(restored.NrFmy, 10)
        self.assertEqual(restored.NrEve, 100)
        self.assertEqual(len(restored.FrfBlocks), 1)
        self.assertEqual(restored.FrfBlocks[0].NrByteFrame, 48)

    def test_multiple_projects(self):
        """Multiple distinct projects are stored separately."""
        for name in ["AAA", "BBB", "CCC"]:
            upload_bench_result(
                name, _BENCH,
                fitted_costs=MicroCosts(),
                store_path=self._store,
            )
        self.assertEqual(project_count(self._store), 3)
        projects = list_projects(store_path=self._store)
        keys = sorted(p["key"] for p in projects)
        self.assertEqual(keys, ["AAA", "BBB", "CCC"])


if __name__ == "__main__":
    unittest.main()
