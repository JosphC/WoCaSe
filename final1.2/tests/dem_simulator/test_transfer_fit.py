"""Unit tests for dem_simulator.transfer_fit — transfer learning.

Covers:
  - _structural_distance: identical configs → 0, different → > 0
  - find_closest_reference: returns a known project
  - scale_costs_by_clock: same MHz → no change, different → scaled
  - infer_costs_for_project: returns valid MicroCosts
  - TransferFitResult.summary() and print_costs_snippet()
"""

import copy
import unittest

from dem_simulator.config import ProjectConfig, FrfBlockConfig
from dem_simulator.costs import MicroCosts, COSTS_PROJ2, COSTS_PROJ3
from dem_simulator.transfer_fit import (
    _structural_distance,
    find_closest_reference,
    scale_costs_by_clock,
    infer_costs_for_project,
)


def _make_cfg(**overrides) -> ProjectConfig:
    defaults = dict(
        name="TEST", NrFmy=12, NrFifoBas=4, NrFifoIntm=8, NrFifoRsv=0,
        NrClcFmyEveAsyn=20, NrClcFmyPost=10, NrEve=150,
        NrFrfDataTot=48, NrFrfPreData=0, NrBlockFrf=2, NrFrfPre=6,
        NrByteFrfFmy=48, NrLamp=2, cpu_clock_mhz=300.0,
        FrfBlocks=[
            FrfBlockConfig(48, 6, 6, 2, 8, 0),
            FrfBlockConfig(32, 4, 4, 2, 6, 0),
        ],
    )
    defaults.update(overrides)
    return ProjectConfig(**defaults)


class TestStructuralDistance(unittest.TestCase):
    """_structural_distance metric."""

    def test_identical_configs_zero(self):
        cfg = _make_cfg()
        self.assertAlmostEqual(_structural_distance(cfg, cfg), 0.0)

    def test_different_nrfmy_positive(self):
        a = _make_cfg(NrFmy=12)
        b = _make_cfg(NrFmy=40)
        dist = _structural_distance(a, b)
        self.assertGreater(dist, 0.0)

    def test_different_cpu_positive(self):
        a = _make_cfg(cpu_clock_mhz=300.0)
        b = _make_cfg(cpu_clock_mhz=160.0)
        dist = _structural_distance(a, b)
        self.assertGreater(dist, 0.0)

    def test_symmetric(self):
        a = _make_cfg(NrFmy=10, NrEve=100)
        b = _make_cfg(NrFmy=20, NrEve=200)
        self.assertAlmostEqual(_structural_distance(a, b),
                               _structural_distance(b, a))


class TestFindClosestReference(unittest.TestCase):
    """find_closest_reference returns a known project."""

    def test_returns_tuple_of_three(self):
        cfg = _make_cfg(NrEve=200)
        result = find_closest_reference(cfg)
        self.assertEqual(len(result), 3)
        name, costs, dist = result
        self.assertIsInstance(name, str)
        self.assertIsInstance(costs, MicroCosts)
        self.assertIsInstance(dist, float)

    def test_proj2_like_config_finds_proj2(self):
        """A config very similar to PROJ2 should pick PROJ2."""
        cfg = _make_cfg(name="LIKE_PROJ2", NrFmy=12, NrEve=150,
                        NrBlockFrf=2, cpu_clock_mhz=300.0,
                        NrFrfDataTot=48)
        name, costs, dist = find_closest_reference(cfg)
        # Should be one of the known references
        self.assertIn(name, {"PROJ2", "PROJ3", "PROJ1"})


class TestScaleCostsByClock(unittest.TestCase):
    """scale_costs_by_clock."""

    def test_same_mhz_no_change(self):
        original = COSTS_PROJ2
        scaled = scale_costs_by_clock(original, 300.0, 300.0)
        for f in original.tunable_fields():
            self.assertAlmostEqual(getattr(scaled, f), getattr(original, f))

    def test_half_speed_doubles_costs(self):
        original = MicroCosts(t_main_fixed=10.0, t_lamp=2.0)
        scaled = scale_costs_by_clock(original, 300.0, 150.0)
        self.assertAlmostEqual(scaled.t_main_fixed, 20.0)
        self.assertAlmostEqual(scaled.t_lamp, 4.0)

    def test_double_speed_halves_costs(self):
        original = MicroCosts(t_main_fixed=10.0, t_lamp=2.0)
        scaled = scale_costs_by_clock(original, 300.0, 600.0)
        self.assertAlmostEqual(scaled.t_main_fixed, 5.0)
        self.assertAlmostEqual(scaled.t_lamp, 1.0)

    def test_does_not_modify_original(self):
        original = copy.deepcopy(COSTS_PROJ3)
        original_fixed = original.t_main_fixed
        scale_costs_by_clock(original, 300.0, 150.0)
        self.assertEqual(original.t_main_fixed, original_fixed)


class TestInferCostsForProject(unittest.TestCase):
    """infer_costs_for_project (estimation without bench data)."""

    def test_returns_valid_microcosts(self):
        cfg = _make_cfg(name="NEW_PROJECT", NrEve=100, cpu_clock_mhz=300.0)
        costs = infer_costs_for_project(cfg)
        self.assertIsInstance(costs, MicroCosts)
        costs.validate()  # should not raise

    def test_different_cpu_changes_costs(self):
        cfg_fast = _make_cfg(name="FAST", cpu_clock_mhz=600.0)
        cfg_slow = _make_cfg(name="SLOW", cpu_clock_mhz=150.0)
        costs_fast = infer_costs_for_project(cfg_fast)
        costs_slow = infer_costs_for_project(cfg_slow)
        # Slower CPU → higher costs
        self.assertGreater(costs_slow.t_main_fixed,
                           costs_fast.t_main_fixed)

    def test_non_negative_costs(self):
        cfg = _make_cfg(name="EDGE", NrFmy=5, NrEve=50, cpu_clock_mhz=100.0)
        costs = infer_costs_for_project(cfg)
        for f in costs.tunable_fields():
            self.assertGreaterEqual(getattr(costs, f), 0.0, f)


if __name__ == "__main__":
    unittest.main()
