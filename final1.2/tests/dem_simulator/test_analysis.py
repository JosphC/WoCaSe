"""Unit tests for dem_simulator.analysis — Monte Carlo, deterministic, sensitivity.

Covers:
  - simulate_peak_runtime returns MonteCarloResult with correct fields
  - MC result: peak >= mean >= min
  - MC result: percentiles p95 ≤ p99 ≤ p999
  - MC result: reproducibility (same seed → same peak)
  - MC result: different seeds → different results
  - build_deterministic_scenarios returns list of (name, Scenario)
  - Deterministic scenarios have valid event counts
"""

import unittest

from dem_simulator.config import ProjectConfig, FrfBlockConfig
from dem_simulator.costs import MicroCosts
from dem_simulator.analysis import (
    MonteCarloResult,
    simulate_peak_runtime,
    build_deterministic_scenarios,
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


class TestMonteCarloResult(unittest.TestCase):
    """simulate_peak_runtime shape and invariants."""

    @classmethod
    def setUpClass(cls):
        """Run MC once with few cycles for speed."""
        cls.result = simulate_peak_runtime(
            _CFG, _COSTS, num_cycles=1000, seed=42,
        )

    def test_returns_montecarlo_result(self):
        self.assertIsInstance(self.result, MonteCarloResult)

    def test_peak_gte_mean(self):
        self.assertGreaterEqual(self.result.peak_us, self.result.mean_us)

    def test_mean_gte_min(self):
        self.assertGreaterEqual(self.result.mean_us, self.result.min_us)

    def test_percentile_ordering(self):
        self.assertLessEqual(self.result.p95_us, self.result.p99_us)
        self.assertLessEqual(self.result.p99_us, self.result.p999_us)

    def test_peak_gte_p999(self):
        self.assertGreaterEqual(self.result.peak_us, self.result.p999_us)

    def test_num_cycles(self):
        self.assertEqual(self.result.num_cycles, 1000)

    def test_seed_stored(self):
        self.assertEqual(self.result.seed, 42)

    def test_elapsed_positive(self):
        self.assertGreater(self.result.elapsed_sec, 0.0)

    def test_ci95_bounds(self):
        self.assertLess(self.result.ci95_low, self.result.ci95_high)
        self.assertLessEqual(self.result.ci95_low, self.result.mean_us)
        self.assertGreaterEqual(self.result.ci95_high, self.result.mean_us)

    def test_stdev_non_negative(self):
        self.assertGreaterEqual(self.result.stdev_us, 0.0)

    def test_all_values_positive(self):
        self.assertGreater(self.result.peak_us, 0.0)
        self.assertGreater(self.result.mean_us, 0.0)
        self.assertGreater(self.result.min_us, 0.0)


class TestMCReproducibility(unittest.TestCase):
    """Same seed produces identical results."""

    def test_same_seed_same_peak(self):
        r1 = simulate_peak_runtime(_CFG, _COSTS, num_cycles=500, seed=123)
        r2 = simulate_peak_runtime(_CFG, _COSTS, num_cycles=500, seed=123)
        self.assertEqual(r1.peak_us, r2.peak_us)
        self.assertEqual(r1.mean_us, r2.mean_us)

    def test_different_seed_different_results(self):
        r1 = simulate_peak_runtime(_CFG, _COSTS, num_cycles=500, seed=1)
        r2 = simulate_peak_runtime(_CFG, _COSTS, num_cycles=500, seed=2)
        # Very unlikely to be identical with different seeds
        self.assertNotEqual(r1.peak_us, r2.peak_us)


class TestDeterministicScenarios(unittest.TestCase):
    """build_deterministic_scenarios factory."""

    def test_returns_list(self):
        scenarios = build_deterministic_scenarios()
        self.assertIsInstance(scenarios, list)
        self.assertGreater(len(scenarios), 0)

    def test_each_is_name_scenario_tuple(self):
        from dem_simulator.scenarios import Scenario
        for name, sc in build_deterministic_scenarios():
            self.assertIsInstance(name, str)
            self.assertIsInstance(sc, Scenario)

    def test_idle_scenario_has_zero_events(self):
        scenarios = build_deterministic_scenarios()
        idle_name, idle_sc = scenarios[0]
        self.assertIn("Idle", idle_name)
        self.assertEqual(idle_sc.nr_events_first, 0)
        self.assertEqual(idle_sc.nr_events_second, 0)


if __name__ == "__main__":
    unittest.main()
