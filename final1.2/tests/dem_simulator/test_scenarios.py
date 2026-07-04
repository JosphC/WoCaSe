"""Unit tests for dem_simulator.scenarios — Scenario and build_scenarios.

Covers:
  - Scenario validation rejects negative events
  - build_scenarios returns 3 scenarios
  - Scenario 1: both batches of events
  - Scenario 2: only first batch
  - Scenario 3: FMY full, displacement only
  - WCS_SCENARIO_KEYS matches ScenarioType enum
  - DEFAULT_CALIBRATIONS has 6 entries
"""

import unittest

from dem_simulator.scenarios import (
    Scenario,
    build_scenarios,
    WCS_SCENARIO_KEYS,
    CALIBRATIONS,
)
from dem_simulator.config import DEFAULT_CALIBRATIONS
from dem_simulator.constants import ScenarioType
from dem_simulator.exceptions import ConfigValidationError


class TestScenarioValidation(unittest.TestCase):
    """Scenario __post_init__ rejects invalid values."""

    def test_negative_first_raises(self):
        with self.assertRaises(ConfigValidationError):
            Scenario("bad", "", nr_events_first=-1, nr_events_second=0,
                     fmy_initially_full=False, frf_slots_full=False)

    def test_negative_second_raises(self):
        with self.assertRaises(ConfigValidationError):
            Scenario("bad", "", nr_events_first=0, nr_events_second=-1,
                     fmy_initially_full=False, frf_slots_full=False)

    def test_zero_events_valid(self):
        sc = Scenario("idle", "", nr_events_first=0, nr_events_second=0,
                      fmy_initially_full=False, frf_slots_full=False)
        self.assertEqual(sc.nr_events_first, 0)


class TestBuildScenarios(unittest.TestCase):
    """build_scenarios() factory function."""

    def test_returns_3_scenarios(self):
        scenarios = build_scenarios(20)
        self.assertEqual(len(scenarios), 3)

    def test_scenario1_both_batches(self):
        s1 = build_scenarios(15)[0]
        self.assertEqual(s1.nr_events_first, 15)
        self.assertEqual(s1.nr_events_second, 15)
        self.assertFalse(s1.fmy_initially_full)

    def test_scenario2_first_batch_only(self):
        s2 = build_scenarios(15)[1]
        self.assertEqual(s2.nr_events_first, 15)
        self.assertEqual(s2.nr_events_second, 0)
        self.assertFalse(s2.fmy_initially_full)

    def test_scenario3_fmy_full_displacement(self):
        s3 = build_scenarios(15)[2]
        self.assertEqual(s3.nr_events_first, 0)
        self.assertEqual(s3.nr_events_second, 15)
        self.assertTrue(s3.fmy_initially_full)
        self.assertTrue(s3.frf_slots_full)
        self.assertTrue(s3.two_phase)

    def test_nr_eve_propagated(self):
        """NrEve is used for event counts, not hardcoded."""
        for nr_eve in [5, 20, 100, 200]:
            scenarios = build_scenarios(nr_eve)
            self.assertEqual(scenarios[0].nr_events_first, nr_eve)
            self.assertEqual(scenarios[0].nr_events_second, nr_eve)
            self.assertEqual(scenarios[2].nr_events_second, nr_eve)

    def test_scenarios_are_frozen(self):
        s1 = build_scenarios(10)[0]
        with self.assertRaises(AttributeError):
            s1.nr_events_first = 99


class TestScenarioKeys(unittest.TestCase):
    """WCS_SCENARIO_KEYS matches ScenarioType enum."""

    def test_keys_match_enum(self):
        expected = tuple(st.value for st in ScenarioType)
        self.assertEqual(WCS_SCENARIO_KEYS, expected)

    def test_three_keys(self):
        self.assertEqual(len(WCS_SCENARIO_KEYS), 3)


class TestCalibrations(unittest.TestCase):
    """DEFAULT_CALIBRATIONS has correct structure."""

    def test_six_calibrations(self):
        self.assertEqual(len(DEFAULT_CALIBRATIONS), 6)

    def test_first_calibration_is_20_10(self):
        self.assertEqual(DEFAULT_CALIBRATIONS[0], (20, 10))

    def test_last_calibration_is_5_3(self):
        self.assertEqual(DEFAULT_CALIBRATIONS[-1], (5, 3))

    def test_all_tuples_of_two_ints(self):
        for asyn, post in DEFAULT_CALIBRATIONS:
            self.assertIsInstance(asyn, int)
            self.assertIsInstance(post, int)
            self.assertGreater(asyn, 0)
            self.assertGreater(post, 0)

    def test_backward_compat_alias(self):
        """CALIBRATIONS alias must equal DEFAULT_CALIBRATIONS."""
        self.assertEqual(CALIBRATIONS, DEFAULT_CALIBRATIONS)


if __name__ == "__main__":
    unittest.main()
