"""Unit tests for dem_simulator.simulation — WCS grid, RMSE, auto_fit.

Covers:
  - simulate_wcs_grid returns correct shape (3 scenarios × 6 calibrations)
  - All simulated values are positive
  - compute_rmse returns 0.0 when sim == bench
  - compute_rmse returns > 0 when sim ≠ bench
  - compute_per_scenario_rmse returns 3 keys
  - auto_fit improves RMSE (or keeps it the same)
  - auto_fit result has all expected attributes
"""

import unittest

from dem_simulator.config import ProjectConfig, FrfBlockConfig, DEFAULT_CALIBRATIONS
from dem_simulator.costs import MicroCosts, COSTS_PROJ2
from dem_simulator.engine import DemMainFunctionSimulator
from dem_simulator.scenarios import WCS_SCENARIO_KEYS, build_scenarios
from dem_simulator.simulation import (
    simulate_wcs_grid,
    compute_rmse,
    compute_per_scenario_rmse,
    auto_fit,
)


def _make_cfg(**overrides) -> ProjectConfig:
    defaults = dict(
        name="TEST", NrFmy=12, NrFifoBas=4, NrFifoIntm=8, NrFifoRsv=0,
        NrClcFmyEveAsyn=20, NrClcFmyPost=10, NrEve=15,
        NrFrfDataTot=48, NrFrfPreData=0, NrBlockFrf=2, NrFrfPre=6,
        NrByteFrfFmy=48, NrLamp=2, cpu_clock_mhz=300.0,
        FrfBlocks=[
            FrfBlockConfig(48, 6, 6, 2, 8, 0),
            FrfBlockConfig(32, 4, 4, 2, 6, 0),
        ],
    )
    defaults.update(overrides)
    return ProjectConfig(**defaults)


_CFG = _make_cfg()
_COSTS = MicroCosts()


class TestSimulateWcsGrid(unittest.TestCase):
    """simulate_wcs_grid shape and value checks."""

    def test_returns_3_scenarios(self):
        grid = simulate_wcs_grid(_CFG, _COSTS)
        self.assertEqual(len(grid), 3)
        for key in WCS_SCENARIO_KEYS:
            self.assertIn(key, grid)

    def test_each_row_has_6_calibrations(self):
        grid = simulate_wcs_grid(_CFG, _COSTS)
        for key, row in grid.items():
            self.assertEqual(len(row), 6, f"{key} should have 6 values")

    def test_all_values_positive(self):
        grid = simulate_wcs_grid(_CFG, _COSTS)
        for key, row in grid.items():
            for i, val in enumerate(row):
                self.assertGreater(val, 0, f"{key}[{i}] should be > 0")

    def test_custom_calibrations(self):
        cals = ((10, 5), (5, 3))
        grid = simulate_wcs_grid(_CFG, _COSTS, calibrations=cals)
        for key, row in grid.items():
            self.assertEqual(len(row), 2)


class TestComputeRmse(unittest.TestCase):
    """RMSE computation."""

    def test_zero_rmse_when_sim_equals_bench(self):
        """If bench values are the simulated values, RMSE should be ~0."""
        grid = simulate_wcs_grid(_CFG, _COSTS)
        # Build bench from simulated values (round to int as bench is int)
        bench = {k: [int(round(v)) for v in row] for k, row in grid.items()}
        rmse = compute_rmse(_CFG, _COSTS, bench)
        self.assertLess(rmse, 1.0, "RMSE should be near 0 when sim ≈ bench")

    def test_positive_rmse_with_offset(self):
        """Bench values offset by 100 → RMSE > 0."""
        grid = simulate_wcs_grid(_CFG, _COSTS)
        bench = {k: [int(round(v)) + 100 for v in row]
                 for k, row in grid.items()}
        rmse = compute_rmse(_CFG, _COSTS, bench)
        self.assertGreater(rmse, 50.0)

    def test_empty_bench_returns_zero(self):
        rmse = compute_rmse(_CFG, _COSTS, {})
        self.assertEqual(rmse, 0.0)


class TestComputePerScenarioRmse(unittest.TestCase):
    """Per-scenario RMSE."""

    def test_returns_3_keys(self):
        grid = simulate_wcs_grid(_CFG, _COSTS)
        bench = {k: [int(round(v)) for v in row] for k, row in grid.items()}
        per_sc = compute_per_scenario_rmse(_CFG, _COSTS, bench)
        self.assertEqual(len(per_sc), 3)
        for key in WCS_SCENARIO_KEYS:
            self.assertIn(key, per_sc)


class TestAutoFit(unittest.TestCase):
    """auto_fit convergence and result shape."""

    def test_fit_improves_or_keeps_rmse(self):
        """Starting from wrong costs, auto_fit should improve RMSE."""
        # Use default costs (wrong) against PROJ2-fitted simulated values
        cfg12 = _make_cfg(name="PROJ2", NrEve=150)
        grid = simulate_wcs_grid(cfg12, COSTS_PROJ2)
        bench = {k: [int(round(v)) for v in row] for k, row in grid.items()}

        # Start from generic defaults (worse fit)
        initial = MicroCosts()
        rmse_before = compute_rmse(cfg12, initial, bench)

        result = auto_fit(cfg12, initial, bench,
                          max_iterations=10,
                          convergence_threshold=0.01)

        self.assertLessEqual(result.rmse_after, rmse_before + 0.01)
        self.assertIsInstance(result.costs, MicroCosts)
        self.assertGreater(result.iterations, 0)
        self.assertIsInstance(result.converged, bool)

    def test_fit_result_has_per_scenario_rmse(self):
        grid = simulate_wcs_grid(_CFG, _COSTS)
        bench = {k: [int(round(v)) for v in row] for k, row in grid.items()}
        result = auto_fit(_CFG, _COSTS, bench, max_iterations=3)
        self.assertEqual(len(result.per_scenario_rmse), 3)

    def test_fit_result_elapsed_positive(self):
        grid = simulate_wcs_grid(_CFG, _COSTS)
        bench = {k: [int(round(v)) for v in row] for k, row in grid.items()}
        result = auto_fit(_CFG, _COSTS, bench, max_iterations=1)
        self.assertGreaterEqual(result.elapsed_sec, 0.0)


if __name__ == "__main__":
    unittest.main()
