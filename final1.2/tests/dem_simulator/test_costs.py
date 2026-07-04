"""Unit tests for dem_simulator.costs — MicroCosts and get_project_costs.

Covers:
  - Default values are non-negative
  - validate() rejects negative costs
  - to_dict / from_dict round-trip
  - tunable_fields returns only t_* fields
  - get_project_costs lookup chain: bench_store → PROJECT_COSTS → transfer → default
  - PROJECT_COSTS contains PROJ1, PROJ2, PROJ3
"""

import unittest

from dem_simulator.costs import (
    MicroCosts,
    COSTS_PROJ1,
    COSTS_PROJ2,
    COSTS_PROJ3,
    PROJECT_COSTS,
    get_project_costs,
)
from dem_simulator.exceptions import ConfigValidationError


class TestMicroCostsDefaults(unittest.TestCase):
    """Default MicroCosts should be valid."""

    def test_all_defaults_non_negative(self):
        mc = MicroCosts()
        mc.validate()  # should not raise
        for fname in mc.tunable_fields():
            self.assertGreaterEqual(getattr(mc, fname), 0.0, fname)

    def test_tunable_fields_start_with_t_or_k(self):
        mc = MicroCosts()
        for f in mc.tunable_fields():
            self.assertTrue(f.startswith(("t_", "k_")),
                            f"Field {f} doesn't start with t_ or k_")

    def test_tunable_fields_sorted(self):
        mc = MicroCosts()
        fields = mc.tunable_fields()
        self.assertEqual(fields, sorted(fields))

    def test_field_count(self):
        """Ensure we have the expected number of tunable fields."""
        mc = MicroCosts()
        actual = len(mc.tunable_fields())
        # Count t_* + k_* fields from the dataclass definition
        import dataclasses
        expected = sum(
            1 for f in dataclasses.fields(mc)
            if f.name.startswith(("t_", "k_"))
        )
        self.assertEqual(actual, expected)


class TestValidation(unittest.TestCase):
    """validate() should reject negative costs."""

    def test_negative_cost_raises(self):
        mc = MicroCosts(t_main_fixed=-1.0)
        with self.assertRaises(ConfigValidationError):
            mc.validate()

    def test_zero_cost_accepted(self):
        mc = MicroCosts(t_frfsrv=0.0)
        mc.validate()  # should not raise


class TestSerialization(unittest.TestCase):
    """to_dict / from_dict round-trip."""

    def test_round_trip_default(self):
        mc = MicroCosts()
        d = mc.to_dict()
        mc2 = MicroCosts.from_dict(d)
        for f in mc.tunable_fields():
            self.assertAlmostEqual(getattr(mc, f), getattr(mc2, f), places=10,
                                   msg=f"Mismatch in {f}")

    def test_round_trip_proj2(self):
        d = COSTS_PROJ2.to_dict()
        restored = MicroCosts.from_dict(d)
        for f in COSTS_PROJ2.tunable_fields():
            self.assertAlmostEqual(getattr(COSTS_PROJ2, f),
                                   getattr(restored, f), places=10)

    def test_from_dict_ignores_unknown_keys(self):
        d = MicroCosts().to_dict()
        d["t_unknown_field"] = 99.0
        mc = MicroCosts.from_dict(d)
        self.assertFalse(hasattr(mc, "t_unknown_field"))

    def test_from_dict_rejects_negative(self):
        d = MicroCosts().to_dict()
        d["t_main_fixed"] = -5.0
        with self.assertRaises(ConfigValidationError):
            MicroCosts.from_dict(d)


class TestProjectCosts(unittest.TestCase):
    """PROJECT_COSTS dict contains expected entries."""

    def test_proj1_present(self):
        # PROJ1 now points to the fully-fitted specific variant
        self.assertIn("PROJ1", PROJECT_COSTS)
        self.assertIsInstance(PROJECT_COSTS["PROJ1"], MicroCosts)
        self.assertIn("PROJ1_0U0_OB6_023", PROJECT_COSTS)

    def test_proj2_present(self):
        self.assertIn("PROJ2", PROJECT_COSTS)
        self.assertIsInstance(PROJECT_COSTS["PROJ2"], MicroCosts)

    def test_proj3_present(self):
        # PROJ3 now points to the fully-fitted specific variant
        self.assertIn("PROJ3", PROJECT_COSTS)
        self.assertIsInstance(PROJECT_COSTS["PROJ3"], MicroCosts)
        self.assertIn("PROJ3_0U0_P16_624", PROJECT_COSTS)

    def test_all_valid(self):
        for name, costs in PROJECT_COSTS.items():
            costs.validate()  # should not raise


class TestGetProjectCosts(unittest.TestCase):
    """get_project_costs lookup chain."""

    def test_known_project_exact(self):
        costs = get_project_costs("PROJ2")
        self.assertIsInstance(costs, MicroCosts)

    def test_known_project_case_insensitive(self):
        costs = get_project_costs("proj3")
        self.assertIsInstance(costs, MicroCosts)

    def test_prefix_match(self):
        """'PROJ2_0U0_OB6_024' should match 'PROJ2' via prefix."""
        costs = get_project_costs("PROJ2_0U0_OB6_024")
        self.assertIsInstance(costs, MicroCosts)

    def test_unknown_project_no_cfg_returns_defaults(self):
        """Unknown project without cfg falls back to MicroCosts()."""
        costs = get_project_costs("UNKNOWN_PROJECT_XYZ")
        self.assertIsInstance(costs, MicroCosts)

    def test_unknown_with_cfg_returns_estimated(self):
        """Unknown project with cfg triggers transfer learning."""
        from dem_simulator.config import ProjectConfig, FrfBlockConfig
        cfg = ProjectConfig(
            name="NEWPROJ", NrFmy=10, NrFifoBas=4, NrFifoIntm=8,
            NrFifoRsv=0, NrClcFmyEveAsyn=20, NrClcFmyPost=10,
            NrEve=100, NrFrfDataTot=40, NrFrfPreData=0, NrBlockFrf=2,
            NrFrfPre=4, NrByteFrfFmy=48, NrLamp=2, cpu_clock_mhz=300.0,
            FrfBlocks=[
                FrfBlockConfig(48, 6, 6, 2, 8, 0),
                FrfBlockConfig(32, 4, 4, 2, 6, 0),
            ],
        )
        costs = get_project_costs("NEWPROJ_XYZ", cfg)
        self.assertIsInstance(costs, MicroCosts)
        # Transfer learning should produce non-default costs
        default = MicroCosts()
        # At least one field should differ from the generic default
        any_different = any(
            getattr(costs, f) != getattr(default, f)
            for f in costs.tunable_fields()
        )
        self.assertTrue(any_different,
                        "Transfer learning should produce non-default costs")


if __name__ == "__main__":
    unittest.main()
