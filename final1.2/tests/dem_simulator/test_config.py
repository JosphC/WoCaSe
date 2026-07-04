"""Unit tests for dem_simulator.config — ProjectConfig, FrfBlockConfig, etc.

Covers:
  - FrfBlockConfig validation (Hold > Tot rejected, non-negative fields)
  - ProjectConfig validation (positive NrFmy, NrClcFmyEveAsyn, etc.)
  - ProjectConfig.summary_dict contains expected keys
  - NrBlockFrf auto-adjustment when mismatched with FrfBlocks length
  - ProjectDefinition structure
  - DEFAULT_CALIBRATIONS imported correctly
"""

import unittest

from dem_simulator.config import (
    FrfBlockConfig,
    ProjectConfig,
    ProjectDefinition,
    DEFAULT_CALIBRATIONS,
)
from dem_simulator.exceptions import ConfigValidationError


class TestFrfBlockConfig(unittest.TestCase):
    """FrfBlockConfig validation."""

    def test_valid_block(self):
        blk = FrfBlockConfig(
            NrByteFrame=48, NrFrfIdxCalMax=6, NrIdxPerClass=6,
            NrFrfHold=2, NrFrfTot=8, LfOptions=0,
        )
        self.assertEqual(blk.NrByteFrame, 48)

    def test_hold_exceeds_tot_raises(self):
        with self.assertRaises(ConfigValidationError):
            FrfBlockConfig(
                NrByteFrame=48, NrFrfIdxCalMax=6, NrIdxPerClass=6,
                NrFrfHold=10, NrFrfTot=8, LfOptions=0,
            )

    def test_negative_byte_frame_raises(self):
        with self.assertRaises(ConfigValidationError):
            FrfBlockConfig(
                NrByteFrame=-1, NrFrfIdxCalMax=6, NrIdxPerClass=6,
                NrFrfHold=2, NrFrfTot=8, LfOptions=0,
            )

    def test_frozen_dataclass(self):
        blk = FrfBlockConfig(48, 6, 6, 2, 8, 0)
        with self.assertRaises(AttributeError):
            blk.NrByteFrame = 99


class TestProjectConfig(unittest.TestCase):
    """ProjectConfig validation and summary."""

    def _make(self, **overrides):
        defaults = dict(
            name="TEST", NrFmy=12, NrFifoBas=4, NrFifoIntm=8, NrFifoRsv=0,
            NrClcFmyEveAsyn=20, NrClcFmyPost=10, NrEve=100,
            NrFrfDataTot=48, NrFrfPreData=0, NrBlockFrf=1, NrFrfPre=6,
            NrByteFrfFmy=48, NrLamp=2, cpu_clock_mhz=300.0,
            FrfBlocks=[FrfBlockConfig(48, 6, 6, 2, 8, 0)],
        )
        defaults.update(overrides)
        return ProjectConfig(**defaults)

    def test_valid_config(self):
        cfg = self._make()
        self.assertEqual(cfg.name, "TEST")
        self.assertEqual(cfg.NrFmy, 12)

    def test_negative_nrfmy_raises(self):
        with self.assertRaises(ConfigValidationError):
            self._make(NrFmy=-1)

    def test_zero_nrfmy_raises(self):
        with self.assertRaises(ConfigValidationError):
            self._make(NrFmy=0)

    def test_zero_eve_asyn_raises(self):
        with self.assertRaises(ConfigValidationError):
            self._make(NrClcFmyEveAsyn=0)

    def test_zero_post_raises(self):
        with self.assertRaises(ConfigValidationError):
            self._make(NrClcFmyPost=0)

    def test_zero_cpu_clock_raises(self):
        with self.assertRaises(ConfigValidationError):
            self._make(cpu_clock_mhz=0.0)

    def test_block_count_mismatch_auto_adjusts(self):
        """NrBlockFrf is adjusted to match actual len(FrfBlocks)."""
        cfg = self._make(NrBlockFrf=5)  # declared 5, but only 1 block
        self.assertEqual(cfg.NrBlockFrf, 1)

    def test_summary_dict_keys(self):
        cfg = self._make()
        summary = cfg.summary_dict()
        expected_keys = {
            "name", "NrFmy", "NrEve", "NrClcFmyEveAsyn", "NrClcFmyPost",
            "NrFrfDataTot", "NrFrfPre", "NrBlockFrf", "NrLamp", "NrClient",
            "NrCore", "NrPtuProfiles", "IsSharedCore",
            "nr_inject_first", "nr_inject_next",
            "has_prio_obd_uds_swap", "gpt_api",
            "cpu_clock_mhz",
        }
        self.assertEqual(set(summary.keys()), expected_keys)

    def test_summary_dict_values(self):
        cfg = self._make(NrFmy=20, NrEve=200)
        summary = cfg.summary_dict()
        self.assertEqual(summary["NrFmy"], 20)
        self.assertEqual(summary["NrEve"], 200)


class TestProjectDefinition(unittest.TestCase):
    """ProjectDefinition structure."""

    def test_construction(self):
        cfg = ProjectConfig(
            name="T", NrFmy=5, NrFifoBas=2, NrFifoIntm=4, NrFifoRsv=0,
            NrClcFmyEveAsyn=10, NrClcFmyPost=5, NrEve=50,
            NrFrfDataTot=20, NrFrfPreData=0, NrBlockFrf=1, NrFrfPre=3,
            NrByteFrfFmy=24,
            FrfBlocks=[FrfBlockConfig(24, 3, 3, 1, 4, 0)],
        )
        pd = ProjectDefinition(
            name="TEST",
            description="Test project",
            default_config=cfg,
            variant_configs={},
            reference_wcs={},
        )
        self.assertEqual(pd.name, "TEST")
        self.assertEqual(pd.calibrations, DEFAULT_CALIBRATIONS)

    def test_custom_calibrations(self):
        cfg = ProjectConfig(
            name="T", NrFmy=5, NrFifoBas=2, NrFifoIntm=4, NrFifoRsv=0,
            NrClcFmyEveAsyn=10, NrClcFmyPost=5, NrEve=50,
            NrFrfDataTot=20, NrFrfPreData=0, NrBlockFrf=1, NrFrfPre=3,
            NrByteFrfFmy=24,
            FrfBlocks=[FrfBlockConfig(24, 3, 3, 1, 4, 0)],
        )
        custom = ((10, 5), (5, 3))
        pd = ProjectDefinition(
            name="T", description="", default_config=cfg,
            variant_configs={}, reference_wcs={},
            calibrations=custom,
        )
        self.assertEqual(pd.calibrations, custom)


if __name__ == "__main__":
    unittest.main()
