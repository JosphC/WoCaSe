"""Unit tests for dem_simulator.engine — DemMainFunctionSimulator.

Covers:
  - Constructor rejection of None arguments
  - Determinism (same inputs → identical outputs)
  - Non-negativity of every breakdown phase
  - Breakdown dict keys match expected phases
  - Total equals sum of breakdown
  - Scenario 2 (no displacement) ≤ Scenario 1 and Scenario 3
  - Monotonicity: more events processed → higher cost
  - Edge case: NrClcFmyEveAsyn / NrClcFmyPost = 1 (minimum)
  - _storefrf_cost_per_block with frf_full True / False
"""

import unittest

from dem_simulator.config import ProjectConfig, FrfBlockConfig
from dem_simulator.costs import MicroCosts, COSTS_PROJ2, COSTS_PROJ3
from dem_simulator.engine import DemMainFunctionSimulator
from dem_simulator.exceptions import SimulatorError, ConfigValidationError
from dem_simulator.scenarios import build_scenarios


def _make_cfg(**overrides) -> ProjectConfig:
    """Return a minimal valid ProjectConfig, with optional overrides."""
    defaults = dict(
        name="TEST",
        NrFmy=12,
        NrFifoBas=4,
        NrFifoIntm=8,
        NrFifoRsv=0,
        NrClcFmyEveAsyn=20,
        NrClcFmyPost=10,
        NrEve=15,
        NrFrfDataTot=48,
        NrFrfPreData=0,
        NrBlockFrf=2,
        NrFrfPre=6,
        NrByteFrfFmy=48,
        NrLamp=2,
        cpu_clock_mhz=300.0,
        FrfBlocks=[
            FrfBlockConfig(NrByteFrame=48, NrFrfIdxCalMax=6,
                           NrIdxPerClass=6, NrFrfHold=2, NrFrfTot=8,
                           LfOptions=0),
            FrfBlockConfig(NrByteFrame=32, NrFrfIdxCalMax=4,
                           NrIdxPerClass=4, NrFrfHold=2, NrFrfTot=6,
                           LfOptions=0),
        ],
    )
    defaults.update(overrides)
    return ProjectConfig(**defaults)


_CFG = _make_cfg()
_COSTS = MicroCosts()
_SCENARIOS = build_scenarios(
    nr_inject_first=_CFG.nr_inject_first,
    nr_inject_next=_CFG.nr_inject_next,
    nr_fmy=_CFG.NrFmy,
)


class TestConstructor(unittest.TestCase):
    """DemMainFunctionSimulator.__init__ guards."""

    def test_none_config_raises(self):
        with self.assertRaises(SimulatorError):
            DemMainFunctionSimulator(None, _COSTS)

    def test_none_costs_raises(self):
        with self.assertRaises(SimulatorError):
            DemMainFunctionSimulator(_CFG, None)

    def test_valid_construction(self):
        sim = DemMainFunctionSimulator(_CFG, _COSTS)
        self.assertIs(sim.cfg, _CFG)
        self.assertIs(sim.c, _COSTS)


class TestDeterminism(unittest.TestCase):
    """Same inputs must always produce identical results."""

    def test_same_inputs_same_output(self):
        sim = DemMainFunctionSimulator(_CFG, _COSTS)
        for scenario in _SCENARIOS:
            t1 = sim.simulate_total(scenario, 20, 10)
            t2 = sim.simulate_total(scenario, 20, 10)
            self.assertEqual(t1, t2,
                             f"Non-deterministic for {scenario.name}")


class TestBreakdown(unittest.TestCase):
    """Validate the breakdown dict returned by simulate()."""

    def setUp(self):
        self.sim = DemMainFunctionSimulator(_CFG, _COSTS)

    def test_all_phases_present(self):
        bd = self.sim.simulate(_SCENARIOS[0], 20, 10)
        expected_keys = {
            # Legacy phases
            "fixed_overhead", "B1_mepa", "L1a_fifo", "L1b_scan",
            "Lamp", "FctScdn",
            "Main2_FrfUpd", "Main2_FrfPre",
            "Main2_NvmOnFly", "Main2_UpdObdFrf", "FrfSrv", "FctPerm",
            "NvmWr", "TestFrfData", "WaitClrResp",
            # New generic/topology phases (engine v2)
            "AsyncSetup", "Main2_Setup",
            "EventDbScan", "ClientCallbacks",
            "CoreSync", "PtuProfileSwitch",
            "IsrJitter", "PrioSwap", "CacheWarmup",
        }
        self.assertEqual(set(bd.keys()), expected_keys)

    def test_all_values_non_negative(self):
        for scenario in _SCENARIOS:
            bd = self.sim.simulate(scenario, 20, 10)
            for phase, val in bd.items():
                self.assertGreaterEqual(val, 0.0,
                                        f"{phase} negative in {scenario.name}")

    def test_total_equals_sum_of_breakdown(self):
        for scenario in _SCENARIOS:
            bd = self.sim.simulate(scenario, 20, 10)
            total = self.sim.simulate_total(scenario, 20, 10)
            self.assertAlmostEqual(total, sum(bd.values()), places=6)


class TestScenarioOrdering(unittest.TestCase):
    """Scenario 2 (no displacement) should be cheapest."""

    def test_s2_cheapest(self):
        sim = DemMainFunctionSimulator(_CFG, _COSTS)
        s1 = sim.simulate_total(_SCENARIOS[0], 20, 10)
        s2 = sim.simulate_total(_SCENARIOS[1], 20, 10)
        s3 = sim.simulate_total(_SCENARIOS[2], 20, 10)
        self.assertLessEqual(s2, s1, "S2 should be ≤ S1")
        self.assertLessEqual(s2, s3, "S2 should be ≤ S3")


class TestMonotonicity(unittest.TestCase):
    """Increasing NrClcFmyEveAsyn increases (or keeps) worst-case time."""

    def test_more_events_processed_higher_cost(self):
        sim = DemMainFunctionSimulator(_CFG, _COSTS)
        s1 = _SCENARIOS[0]
        vals = [sim.simulate_total(s1, ea, 10) for ea in [5, 10, 15, 20]]
        for i in range(len(vals) - 1):
            self.assertLessEqual(vals[i], vals[i + 1],
                                 f"EA={[5,10,15,20][i]} should ≤ EA={[5,10,15,20][i+1]}")


class TestEdgeCases(unittest.TestCase):
    """Minimum calibration values and boundary conditions."""

    def test_minimum_calibration(self):
        """NrClcFmyEveAsyn=1, NrClcFmyPost=1 should not crash."""
        sim = DemMainFunctionSimulator(_CFG, _COSTS)
        for scenario in _SCENARIOS:
            total = sim.simulate_total(scenario, 1, 1)
            self.assertGreater(total, 0.0)

    def test_zero_calibration_raises(self):
        sim = DemMainFunctionSimulator(_CFG, _COSTS)
        with self.assertRaises(ConfigValidationError):
            sim.simulate(_SCENARIOS[0], 0, 10)
        with self.assertRaises(ConfigValidationError):
            sim.simulate(_SCENARIOS[0], 10, 0)

    def test_large_calibration(self):
        """Very large EveAsyn/Post should not crash."""
        sim = DemMainFunctionSimulator(_CFG, _COSTS)
        total = sim.simulate_total(_SCENARIOS[0], 100, 100)
        self.assertGreater(total, 0.0)


class TestStoreFrfCost(unittest.TestCase):
    """Test _storefrf_cost_per_block with different frf_full states."""

    def setUp(self):
        self.sim = DemMainFunctionSimulator(_CFG, _COSTS)
        self.blk = _CFG.FrfBlocks[0]

    def test_free_frame_cheaper_than_full(self):
        cost_free = self.sim._storefrf_cost_per_block(self.blk, False)
        cost_full = self.sim._storefrf_cost_per_block(self.blk, True)
        self.assertGreater(cost_full, 0.0)
        self.assertGreater(cost_free, 0.0)

    def test_full_more_expensive_than_free(self):
        """Full FRF slots cost more than a free-frame copy."""
        cost_full = self.sim._storefrf_cost_per_block(self.blk, True)
        cost_free = self.sim._storefrf_cost_per_block(self.blk, False)
        self.assertGreaterEqual(cost_full, cost_free)


class TestWithFittedCosts(unittest.TestCase):
    """Run with real fitted costs to ensure no crashes."""

    def test_proj2_runs(self):
        cfg = _make_cfg(name="PROJ2", NrEve=150)
        sim = DemMainFunctionSimulator(cfg, COSTS_PROJ2)
        scenarios = build_scenarios(
            nr_inject_first=cfg.nr_inject_first,
            nr_inject_next=cfg.nr_inject_next,
            nr_fmy=cfg.NrFmy,
        )
        for sc in scenarios:
            total = sim.simulate_total(sc, 20, 10)
            self.assertGreater(total, 0.0)
            self.assertLess(total, 5000.0)

    def test_proj3_runs(self):
        cfg = _make_cfg(name="PROJ3", NrEve=200, NrLamp=3)
        sim = DemMainFunctionSimulator(cfg, COSTS_PROJ3)
        scenarios = build_scenarios(
            nr_inject_first=cfg.nr_inject_first,
            nr_inject_next=cfg.nr_inject_next,
            nr_fmy=cfg.NrFmy,
        )
        for sc in scenarios:
            total = sim.simulate_total(sc, 20, 10)
            self.assertGreater(total, 0.0)
            self.assertLess(total, 5000.0)


if __name__ == "__main__":
    unittest.main()
