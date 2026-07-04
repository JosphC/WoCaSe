"""Unit tests for dem_simulator.constants — values and enums.

Covers:
  - Threshold values are positive
  - Elementary cost constants are non-negative
  - Monte Carlo defaults are reasonable
  - Auto-fit defaults are reasonable
  - ScenarioType enum has 3 members
  - FIT_DELTA_FRACTIONS contains both positive and negative values
"""

import unittest

from dem_simulator.constants import (
    BYTE_COPY_COST_US,
    NVM_WRITE_COST_US,
    TEST_FRF_DATA_COST_US,
    WAIT_CLR_RESP_COST_US,
    MC_DEFAULT_CYCLES,
    MC_DEFAULT_SEED,
    MC_IRQ_MU,
    MC_IRQ_SIGMA,
    FIT_MAX_ITERATIONS,
    FIT_CONVERGENCE_THRESHOLD,
    FIT_DELTA_FRACTIONS,
    ScenarioType,
)


class TestElementaryCosts(unittest.TestCase):
    def test_byte_copy_non_negative(self):
        self.assertGreater(BYTE_COPY_COST_US, 0)

    def test_nvm_write_non_negative(self):
        self.assertGreater(NVM_WRITE_COST_US, 0)

    def test_test_frf_data_non_negative(self):
        self.assertGreater(TEST_FRF_DATA_COST_US, 0)

    def test_wait_clr_resp_non_negative(self):
        self.assertGreater(WAIT_CLR_RESP_COST_US, 0)


class TestMonteCarloDefaults(unittest.TestCase):
    def test_cycles_positive(self):
        self.assertGreater(MC_DEFAULT_CYCLES, 0)

    def test_seed_is_int(self):
        self.assertIsInstance(MC_DEFAULT_SEED, int)

    def test_irq_sigma_positive(self):
        self.assertGreater(MC_IRQ_SIGMA, 0)


class TestFitDefaults(unittest.TestCase):
    def test_max_iterations_positive(self):
        self.assertGreater(FIT_MAX_ITERATIONS, 0)

    def test_convergence_threshold_positive(self):
        self.assertGreater(FIT_CONVERGENCE_THRESHOLD, 0)

    def test_delta_fractions_has_positive_and_negative(self):
        has_pos = any(d > 0 for d in FIT_DELTA_FRACTIONS)
        has_neg = any(d < 0 for d in FIT_DELTA_FRACTIONS)
        self.assertTrue(has_pos, "Should have positive deltas")
        self.assertTrue(has_neg, "Should have negative deltas")

    def test_delta_fractions_symmetric(self):
        """Positive and negative deltas should be roughly symmetric."""
        positives = sorted(d for d in FIT_DELTA_FRACTIONS if d > 0)
        negatives = sorted(-d for d in FIT_DELTA_FRACTIONS if d < 0)
        self.assertEqual(positives, negatives)


class TestScenarioType(unittest.TestCase):
    def test_three_members(self):
        self.assertEqual(len(ScenarioType), 3)

    def test_values(self):
        self.assertEqual(ScenarioType.SCENARIO_1.value, "scenario_1")
        self.assertEqual(ScenarioType.SCENARIO_2.value, "scenario_2")
        self.assertEqual(ScenarioType.SCENARIO_3.value, "scenario_3")


if __name__ == "__main__":
    unittest.main()
