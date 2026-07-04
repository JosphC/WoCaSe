"""Project configuration dataclasses.

Contains FrfBlockConfig, ProjectConfig, and ProjectDefinition.
Concrete values are extracted dynamically from the project's C sources
by ``dem_simulator.extractor``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal

from dem_simulator.exceptions import ConfigValidationError

logger = logging.getLogger("dem_simulator")


# ==============================================================================
# Validation helpers
# ==============================================================================

def _validate_non_negative(value: int | float, name: str) -> None:
    """Raise ConfigValidationError if *value* is negative."""
    if value < 0:
        raise ConfigValidationError(f"{name} must be >= 0, got {value}")


def _validate_positive(value: int | float, name: str) -> None:
    """Raise ConfigValidationError if *value* is not positive."""
    if value <= 0:
        raise ConfigValidationError(f"{name} must be > 0, got {value}")


# ==============================================================================
# FrfBlockConfig
# ==============================================================================

@dataclass(frozen=True)
class FrfBlockConfig:
    """One freeze-frame block configuration.

    Attributes
    ----------
    NrByteFrame : int
        Number of bytes per freeze frame.
    NrFrfIdxCalMax : int
        Maximum calibratable FRF index count.
    NrIdxPerClass : int
        Number of data indices per FRF class.
    NrFrfHold : int
        Number of frames to hold (not shiftable).
    NrFrfTot : int
        Total frames allocated for this block.
    LfOptions : int
        Bit field; bit 0 = FIXED_CLAS.
    """
    NrByteFrame: int
    NrFrfIdxCalMax: int
    NrIdxPerClass: int
    NrFrfHold: int
    NrFrfTot: int
    LfOptions: int

    def __post_init__(self) -> None:
        _validate_non_negative(self.NrByteFrame, "NrByteFrame")
        _validate_non_negative(self.NrIdxPerClass, "NrIdxPerClass")
        _validate_non_negative(self.NrFrfHold, "NrFrfHold")
        _validate_non_negative(self.NrFrfTot, "NrFrfTot")
        if self.NrFrfHold > self.NrFrfTot:
            raise ConfigValidationError(
                f"NrFrfHold ({self.NrFrfHold}) cannot exceed "
                f"NrFrfTot ({self.NrFrfTot})"
            )


# ==============================================================================
# ProjectConfig
# ==============================================================================

@dataclass
class ProjectConfig:
    """All DEM configuration parameters that influence MainFunction runtime.

    Each field maps directly to a generated constant from ``icsp_dem_cnf.c``
    or a calibratable value from the ARXML specification.
    """
    name: str

    # --- FMY ---
    NrFmy: int            # failure memory entries
    NrFifoBas: int        # basic FIFO size
    NrFifoIntm: int       # intermediate FIFO size
    NrFifoRsv: int

    # --- Calibratable ---
    NrClcFmyEveAsyn: int  # max async events per recurrence  (cal)
    NrClcFmyPost: int     # max deferred post-processing      (cal)

    # --- Events ---
    NrEve: int            # total number of DEM events

    # --- FRF ---
    NrFrfDataTot: int     # total FRF data elements
    NrFrfPreData: int     # previous-value pre-data entries
    NrBlockFrf: int       # number of FRF blocks
    NrFrfPre: int         # prestored freeze frames
    NrByteFrfFmy: int     # bytes per FMY FRF
    FrfBlocks: List[FrfBlockConfig] = field(default_factory=list)

    # --- Callbacks ---
    NrCallbackTypes: int = 3
    NrFctDtcStatusChangedTot: int = 1
    NrFctEventStatusChanged: int = 1
    NrFctFrfDataChanged: int = 1

    # --- Lamp ---
    NrLamp: int = 0

    # --- NVM ---
    NrFmyBufNvmWr: int = 1

    # --- Client ---
    NrClient: int = 6

    # --- Runtime topology (generic, project-agnostic) ---
    NrCore: int = 1
    NrPtuProfiles: int = 1
    IsSharedCore: bool = False

    # --- Hardware ---
    cpu_clock_mhz: float = 300.0

    # --- Instrumentation-derived WCS injection ---
    nr_inject_first: int = 20   # count in lc_enable_first_nr_fmy_events block
    nr_inject_next: int = 20    # count in lc_enable_next_nr_fmy_events block

    # --- Platform/runtime metadata ---
    has_prio_obd_uds_swap: bool = False
    gpt_api: Literal["iopt_gpt", "gpt"] = "iopt_gpt"

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate all fields; raise ConfigValidationError on problems."""
        _validate_positive(self.NrFmy, "NrFmy")
        _validate_non_negative(self.NrFifoBas, "NrFifoBas")
        _validate_non_negative(self.NrFifoIntm, "NrFifoIntm")
        _validate_non_negative(self.NrFifoRsv, "NrFifoRsv")
        _validate_positive(self.NrClcFmyEveAsyn, "NrClcFmyEveAsyn")
        _validate_positive(self.NrClcFmyPost, "NrClcFmyPost")
        _validate_non_negative(self.NrEve, "NrEve")
        _validate_positive(self.NrCore, "NrCore")
        _validate_positive(self.NrPtuProfiles, "NrPtuProfiles")
        _validate_non_negative(self.nr_inject_first, "nr_inject_first")
        _validate_non_negative(self.nr_inject_next, "nr_inject_next")
        _validate_non_negative(self.NrFrfDataTot, "NrFrfDataTot")
        _validate_non_negative(self.NrFrfPre, "NrFrfPre")
        _validate_positive(self.cpu_clock_mhz, "cpu_clock_mhz")
        if self.gpt_api not in ("iopt_gpt", "gpt"):
            raise ConfigValidationError(
                f"gpt_api must be 'iopt_gpt' or 'gpt', got {self.gpt_api!r}"
            )
        if self.NrBlockFrf != len(self.FrfBlocks):
            logger.warning(
                "NrBlockFrf (%d) does not match len(FrfBlocks) (%d) for %s; "
                "adjusting NrBlockFrf.",
                self.NrBlockFrf, len(self.FrfBlocks), self.name,
            )
            self.NrBlockFrf = len(self.FrfBlocks)

    def summary_dict(self) -> Dict[str, Any]:
        """Return a serialisable summary of the key config parameters."""
        return {
            "name": self.name,
            "NrFmy": self.NrFmy,
            "NrEve": self.NrEve,
            "nr_inject_first": self.nr_inject_first,
            "nr_inject_next": self.nr_inject_next,
            "NrClcFmyEveAsyn": self.NrClcFmyEveAsyn,
            "NrClcFmyPost": self.NrClcFmyPost,
            "NrFrfDataTot": self.NrFrfDataTot,
            "NrFrfPre": self.NrFrfPre,
            "NrBlockFrf": self.NrBlockFrf,
            "NrLamp": self.NrLamp,
            "NrClient": self.NrClient,
            "NrCore": self.NrCore,
            "NrPtuProfiles": self.NrPtuProfiles,
            "IsSharedCore": self.IsSharedCore,
            "cpu_clock_mhz": self.cpu_clock_mhz,
            "gpt_api": self.gpt_api,
            "has_prio_obd_uds_swap": self.has_prio_obd_uds_swap,
        }


# ==============================================================================
# ProjectDefinition
# ==============================================================================

from typing import Tuple as _Tuple

# Default calibration pairs (NrClcFmyEveAsyn, NrClcFmyPost)
# Used when no project-specific calibrations are provided.
DEFAULT_CALIBRATIONS: _Tuple[_Tuple[int, int], ...] = (
    (20, 10),   # Calibration 1
    (10, 10),   # Calibration 2
    (10,  5),   # Calibration 3
    ( 5,  5),   # Calibration 4
    ( 5,  4),   # Calibration 5
    ( 5,  3),   # Calibration 6
)


@dataclass
class ProjectDefinition:
    """Bundles all project-specific data needed by the simulator.

    Attributes
    ----------
    name : str
        Short project key (e.g. ``"PROJ3"``).
    description : str
        Human-readable project descriptor shown in reports.
    default_config : ProjectConfig
        The primary (PTU0_EU) configuration.
    variant_configs : Dict[str, ProjectConfig]
        Named variants (PTU1, PTU2, ...) with overridden parameters.
    reference_wcs : Dict[str, List[int]]
        Bench-measured reference values per WCS scenario.
        Keys match ``ScenarioType.value``; each value is a list of N ints
        (one per calibration pair in ``calibrations`` order).
        Empty dict if no bench data is available.
    calibrations : tuple[tuple[int, int], ...]
        Ordered (NrClcFmyEveAsyn, NrClcFmyPost) pairs used for
        WCS measurement on the bench.  Defaults to the standard 6.
    """
    name: str
    description: str
    default_config: ProjectConfig
    variant_configs: Dict[str, ProjectConfig]
    reference_wcs: Dict[str, List[int]]
    calibrations: _Tuple[_Tuple[int, int], ...] = DEFAULT_CALIBRATIONS



