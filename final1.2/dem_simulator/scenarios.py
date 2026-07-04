"""Scenario definitions matching the WCS calibration measurement procedure.

Each scenario maps 1:1 to the measurement steps documented in the
WCS runtime specification.  The calibration flags modelled are::

    lc_enable_runtime_dem_main      -- gates the runtime measurement
    lc_enable_first_nr_fmy_events   -- inject first batch of events
    lc_enable_next_nr_fmy_events    -- inject second batch (higher-prio)

The number of events per batch is extracted from instrumentation in
``icsp_dem_main.c`` (count of ``ACTION_ERRM_ResultDiag`` calls inside each
calibration branch), then capped by ``NrFmy`` for effective per-recurrence
FMY impact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from dem_simulator.exceptions import ConfigValidationError
from dem_simulator.constants import ScenarioType


# ==============================================================================
# Scenario dataclass
# ==============================================================================

@dataclass(frozen=True)
class Scenario:
    """Defines a worst-case scenario for simulation.

    Attributes
    ----------
    name : str
        Human-readable scenario name.
    description : str
        Detailed description of the scenario conditions.
    nr_events_first : int
        Events entering in L1a (first batch, filling empty FMY slots).
        Triggered by ``lc_enable_first_nr_fmy_events = 1``.
    nr_events_second : int
        Additional higher-prio events that trigger displacement.
        Triggered by ``lc_enable_next_nr_fmy_events = 1``.
    fmy_initially_full : bool
        If True, FMY is already full at the start of the **measured**
        recurrence (Scenario 3: FMY was filled in a preceding phase).
    frf_slots_full : bool
        If True, all FRF frame slots are occupied (requires frame shifting).
    two_phase : bool
        If True, the scenario requires two separate measurement phases.
        Phase 1 fills FMY (not measured), Phase 2 displaces (measured).
        This corresponds to Scenario 3's calibration procedure.
    calibration_steps : tuple[str, ...]
        Ordered calibration commands executed on the ECU to set up this
        scenario, for documentation / traceability.
    """
    name: str
    description: str
    nr_events_first: int
    nr_events_second: int
    fmy_initially_full: bool
    frf_slots_full: bool
    two_phase: bool = False
    calibration_steps: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.nr_events_first < 0:
            raise ConfigValidationError(
                f"nr_events_first must be >= 0, got {self.nr_events_first}"
            )
        if self.nr_events_second < 0:
            raise ConfigValidationError(
                f"nr_events_second must be >= 0, got {self.nr_events_second}"
            )


# ==============================================================================
# Calibration steps (documentation strings)
# ==============================================================================

_S1_STEPS: Tuple[str, ...] = (
    "Set lc_enable_runtime_dem_main = 0",
    "Delete complete failure memory: Icsp_Dem_Main_LvClrFmyMan (0 -> 1)",
    "  -> Icsp_Dem_Fmy_EventId[0..NrFmy-1] must be empty: '-'",
    "Set lc_enable_first_nr_fmy_events = 1",
    "Set lc_enable_next_nr_fmy_events = 1",
    "Set lc_enable_runtime_dem_main = 1",
)

_S2_STEPS: Tuple[str, ...] = (
    "Set lc_enable_runtime_dem_main = 0",
    "Delete complete failure memory: Icsp_Dem_Main_LvClrFmyMan (0 -> 1)",
    "  -> Icsp_Dem_Fmy_EventId[0..NrFmy-1] must be empty: '-'",
    "Set lc_enable_first_nr_fmy_events = 1",
    "Set lc_enable_next_nr_fmy_events = 0",
    "Set lc_enable_runtime_dem_main = 1",
)

_S3_STEPS: Tuple[str, ...] = (
    "--- Phase 1: fill FMY (not measured) ---",
    "Set lc_enable_runtime_dem_main = 0",
    "Delete complete failure memory: Icsp_Dem_Main_LvClrFmyMan (0 -> 1)",
    "  -> Icsp_Dem_Fmy_EventId[0..NrFmy-1] must be empty: '-'",
    "Set lc_enable_first_nr_fmy_events = 1",
    "Set lc_enable_next_nr_fmy_events = 0",
    "Set lc_enable_runtime_dem_main = 1",
    "--- Phase 2: displace with higher-prio (MEASURED) ---",
    "Set lc_enable_runtime_dem_main = 0",
    "Set lc_enable_next_nr_fmy_events = 1",
    "Set lc_enable_runtime_dem_main = 1",
)


# ==============================================================================
# build_scenarios  —  constructs Scenario tuple from ProjectConfig
# ==============================================================================

def build_scenarios(
    nr_inject_first: int,
    nr_inject_next: Optional[int] = None,
    nr_fmy: Optional[int] = None,
) -> Tuple[Scenario, ...]:
    """Build the three WCS scenarios from instrumentation-derived injection.

    Parameters
    ----------
    nr_inject_first : int
        Number of diagnostic injections in the first WCS branch
        (``lc_enable_first_nr_fmy_events``).
    nr_inject_next : int, optional
        Number of diagnostic injections in the second WCS branch
        (``lc_enable_next_nr_fmy_events``).  Defaults to *nr_inject_first*
        for backwards-compatibility with the single-argument legacy API
        used by older tests.
    nr_fmy : int, optional
        Failure memory size used to cap effective event impact in one
        recurrence.  Defaults to *nr_inject_first*.

    Returns
    -------
    tuple[Scenario, Scenario, Scenario]
        (S1, S2, S3) ready for simulation.
    """
    if nr_inject_next is None:
        nr_inject_next = nr_inject_first
    if nr_fmy is None:
        nr_fmy = nr_inject_first

    eff_first = min(max(0, nr_inject_first), max(0, nr_fmy))
    eff_next = min(max(0, nr_inject_next), max(0, nr_fmy))

    return (
        Scenario(
            name="Scenario 1 (extremely rare)",
            # description=(
            #     f"{eff_first} INTM/FAIL events enter + {eff_next} additional "
            #     f"higher-prio events enter too (in one recurrence). "
            #     f"lc_enable_first=1, lc_enable_next=1."
            # ),
            description=(
                f"NrFmy (e.g {eff_first}) INTM or FAIL events enter plus "
                f"NrFmy (e.g {eff_next}) additional INTM or FAIL events with higher prio enter too  "
                f"(in one recurrence)"
            ),
            nr_events_first=eff_first,
            nr_events_second=eff_next,
            fmy_initially_full=False,
            frf_slots_full=False,
            two_phase=False,
            calibration_steps=_S1_STEPS,
        ),
        Scenario(
            name="Scenario 2 (rare)",
            # description=(
            #     f"{eff_first} INTM/FAIL events enter (in one recurrence). "
            #     f"lc_enable_first=1, lc_enable_next=0."
            # ),
            description=(
                f"NrFmy (e.g {eff_first}) INTM or FAIL events enter "
                f"(in one recurrence)"
            ),
            nr_events_first=eff_first,
            nr_events_second=0,
            fmy_initially_full=False,
            frf_slots_full=False,
            two_phase=False,
            calibration_steps=_S2_STEPS,
        ),
        Scenario(
            name="Scenario 3 (rare)",
            # description=(
            #     f"FMY already full (filled in Phase 1), then {eff_next} "
            #     f"higher-prio events displace existing entries (Phase 2). "
            #     f"Phase 2: lc_enable_next=1."
            # ),
            description=(
                f"FMY is already full and "
                f"NrFmy (e.g {eff_next}) INTM or FAIL higher prio events enter "
                f"(in one recurrence)"
            ),
            nr_events_first=0,
            nr_events_second=eff_next,
            fmy_initially_full=True,
            frf_slots_full=True,
            two_phase=True,
            calibration_steps=_S3_STEPS,
        ),
    )


# Legacy constant — used when no ProjectConfig is available (e.g. selftest).
# Matches the old hard-coded value.
SCENARIOS: Tuple[Scenario, ...] = build_scenarios(
    nr_inject_first=20,
    nr_inject_next=20,
    nr_fmy=20,
)


# WCS scenario key mapping (for Excel and reference data)
WCS_SCENARIO_KEYS: Tuple[str, ...] = tuple(st.value for st in ScenarioType)

# Backward-compatible alias — imports still work but prefer
# ``project.calibrations`` or ``DEFAULT_CALIBRATIONS`` from config.py.
from dem_simulator.config import DEFAULT_CALIBRATIONS  # noqa: E402
CALIBRATIONS = DEFAULT_CALIBRATIONS
