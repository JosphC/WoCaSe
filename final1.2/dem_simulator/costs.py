"""Micro-cost model: per-operation costs in microseconds.

Contains the MicroCosts dataclass and fitted cost sets for PROJ2 / PROJ3.

NOTE: project codenames in this module (PROJ1..PROJ6) are anonymized
placeholders for real company ECU projects. The fitted numeric values
are kept unchanged as illustrative calibration data for the thesis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from dem_simulator.exceptions import ConfigValidationError

_log = logging.getLogger("dem_simulator")


# ==============================================================================
# MicroCosts dataclass
# ==============================================================================

@dataclass
class MicroCosts:
    """Per-operation costs in microseconds.

    Each field represents the empirically fitted cost of one elementary
    processing step inside ``Icsp_Dem_MainFunction``.  The costs combine
    pure CPU time with average cache-miss, RTE, and memory-access overhead
    for the respective ECU target.
    """

    # --- Fixed overhead of MainFunction ---
    t_main_fixed: float = 8.0          # timer read, config check, ChkClrReq,
                                        # WaitClrResp, TestFrfData, NVM, etc.
    t_gpt_read: float = 0.5            # per timer sample (old + new)

    # --- ClcMainTranB1: per confirmed-threshold entry ---
    t_b1_per_entry: float = 3.0        # CopyEntry + TreatEntryCfm + UpdLamp +
                                        # TreatPost + Prio + CopyBack

    # --- ClcMainTranL1a: per FIFO event ---
    t_async_recurrence: float = 0.0   # fixed async-path cost per measured recurrence
    t_l1a_per_event_new: float = 4.5   # FifoRemove + UpdFirstLast + ProcCombGrp +
                                        # MakeNewEntry (empty slot available)
    t_l1a_per_event_displace: float = 8.0  # same but with Prio_GetLoPrio +
                                            # HistoryResortingSingle + erase old
    t_resort_per_entry: float = 0.0    # additional NrFmy-scaled displacement tax

    # --- ClcMainTranL1b: per FMY entry (always NrFmy iterations) ---
    t_l1b_per_entry_empty: float = 0.3   # just check EventId < NrEve
    t_l1b_per_entry_valid: float = 1.5   # TreatEntrySelfClrL1b or TreatEntryFailPassL1b
    t_l1b_resorting: float = 2.0         # HistoryResorting() if entries erased

    # --- ClcMainTranLamp: 1 entry per call ---
    t_lamp: float = 1.0

    # --- ClcMain2 / ClcFrfUpdMain2: per deferred entry ---
    t_main2_recurrence: float = 0.0   # fixed Main2 path cost per measured recurrence
    t_deferred_base: float = 2.5       # GetForDeferredProcessing + PrepEntryFrfUpd +
                                        # ClcStatusByte + callback triggers + NvmWr

    # --- StoreFrf: per block per deferred entry ---
    t_storefrf_no_update: float = 0.1    # block not requested
    t_storefrf_free_frame: float = 1.2   # free frame -> GetFrfPre + UpdFrame(Copy)
    t_storefrf_full_shift: float = 2.5   # full -> shift frames + UpdFrame
    t_collect_per_idx: float = 0.05      # per NrIdxPerClass RTE data read

    # --- CollectDataForBlock (called inside UpdFrame when no prestored) ---
    t_collect_fixed: float = 0.3
    t_collect_per_entry: float = 0.3

    # --- Probability of FrfPre hit (0.0 => worst-case all collect) ---
    p_frfpre_hit: float = 0.0

    # --- ClcFrfPre: per prestored FRF processed ---
    t_frfpre_per_entry: float = 1.0

    # --- NVM on-fly treatment ---
    t_nvm_onfly: float = 0.5

    # --- FrfSrv_GetFrfData (normally 0 unless tester connected) ---
    t_frfsrv: float = 0.0

    # --- FctPerm / FctScdn function pointers ---
    t_fct_perm: float = 1.0
    t_fct_scdn: float = 0.5

    # --- UpdObdFrf ---
    t_upd_obd_frf: float = 0.3

    # --- Project-level scalar (compiler/platform/cache/RTE wrapper spread) ---
    t_client_per_client: float = 0.0      # per registered DEM client callback chain
    t_event_db_per_event: float = 0.0     # per-event table walk / bookkeeping overhead
    t_core_sync_per_peer: float = 0.0     # per additional peer core in barrier sync
    t_shared_core_penalty: float = 0.0    # fixed penalty when DEM runs on shared core
    t_ptu_profile_penalty: float = 0.0    # incremental penalty for extra PTU profiles

    # --- ISR preemption jitter (us per MainFunction call) ---
    # Models hard interrupts (CAN, GPT, ADC ISRs) that fire inside the
    # Gpt_GetSystemTime() measurement window and inflate wall-clock time.
    # Derive from bench: (with_interrupts - without_interrupts) column in Tabelle2.
    # For PROJ4 Cal1 (20/10): ~110 µs;  Cal4 (5/3): ~0 µs  → typical seed: 80 µs.
    t_isr_jitter: float = 0.0

    # --- OBD/UDS priority-swap overhead (us per MainFunction call) ---
    # Added only when ProjectConfig.has_prio_obd_uds_swap is True.
    # Derives from Tabelle2: (without_int/with_prio - without_int/without_prio).
    # For PROJ4: Cal1 ≈ 330 µs, Cal2 ≈ 390 µs, Cal3 ≈ 270 µs, Cal4 ≈ 210 µs.
    t_prio_swap: float = 0.0

    # --- Cold-cache penalty per FRF block (us) ---
    # Models first-touch cache misses on PFLASH/PSPR when FRF blocks are
    # accessed for the first time in a measurement window.
    # Typical range: 5-20 µs per block on TC3xx.
    t_cache_miss_per_block: float = 0.0

    k_scenario2_variable: float = 1.0
    k_proj: float = 1.0

    # ------------------------------------------------------------------
    # Per-field metadata used by the fitter and transfer-learning.
    #
    # ``BOUNDS``  — physically plausible (min, max) per field (µs / unitless).
    #               The fitter clamps trial values inside the box, preventing
    #               degenerate fits such as ``t_main_fixed = 0.14`` µs.
    # ``CPU_BOUND_FIELDS`` — costs that scale ~linearly with the CPU clock
    #               (pure ALU / pipeline work).  All other tunable fields
    #               are assumed memory / IO bound and are NOT rescaled when
    #               porting costs to another CPU frequency.
    # ``ZERO_INIT_STEPS`` — additive seed values (µs) tried for fields that
    #               start at exactly 0.  Without these, a purely
    #               multiplicative descent can never escape 0.
    # ------------------------------------------------------------------
    BOUNDS: Dict[str, tuple[float, float]] = None  # type: ignore[assignment]
    CPU_BOUND_FIELDS: frozenset[str] = frozenset()  # populated below
    ZERO_INIT_STEPS: Dict[str, tuple[float, ...]] = None  # type: ignore[assignment]

    def validate(self) -> None:
        """Ensure all costs are non-negative."""
        for fname in self.tunable_fields():
            val = getattr(self, fname)
            if fname.startswith("k_"):
                if val <= 0:
                    raise ConfigValidationError(
                        f"Micro-cost factor {fname} must be > 0, got {val}"
                    )
                continue
            if val < 0:
                raise ConfigValidationError(
                    f"Micro-cost {fname} must be >= 0, got {val}"
                )
        if not (0.0 <= self.p_frfpre_hit <= 1.0):
            raise ConfigValidationError(
                f"p_frfpre_hit must be within [0,1], got {self.p_frfpre_hit}"
            )
    def tunable_fields(self) -> List[str]:
        """Return sorted list of tunable field names (``t_*`` and ``k_*``)."""
        fields = [f for f in vars(self) if f.startswith(("t_", "k_"))]
        return sorted(fields)

    def to_dict(self) -> Dict[str, float]:
        """Serialise all tunable costs to a dict."""
        d = {f: getattr(self, f) for f in self.tunable_fields()}
        d["p_frfpre_hit"] = self.p_frfpre_hit
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "MicroCosts":
        """Construct from a dict (e.g. loaded from JSON or SQLite).

        Round-trip preserving: this method does **not** clamp values
        into :data:`BOUNDS` — the bench store must return exactly what
        it was given.  The fitter (:func:`auto_fit`) is responsible for
        clamping the seed before running the descent, so corrupted
        legacy values can never propagate into trial costs.
        """
        known = {f for f in vars(cls()) if f.startswith(("t_", "k_"))}
        known.add("p_frfpre_hit")
        filtered = {k: v for k, v in d.items() if k in known}
        obj = cls(**filtered)
        obj.validate()
        return obj

    # ------------------------------------------------------------------
    # Bound / step access helpers (used by simulation.auto_fit).
    # ------------------------------------------------------------------

    @classmethod
    def bounds_for(cls, fname: str) -> tuple[float, float]:
        """Return ``(lo, hi)`` for *fname* with a safe default if absent."""
        if cls.BOUNDS and fname in cls.BOUNDS:
            return cls.BOUNDS[fname]
        if fname.startswith("k_"):
            return (0.1, 5.0)
        return (0.0, 200.0)

    @classmethod
    def clamp(cls, fname: str, value: float) -> float:
        """Clip *value* into the physical bounds defined for *fname*."""
        lo, hi = cls.bounds_for(fname)
        if value < lo:
            return lo
        if value > hi:
            return hi
        return value

    @classmethod
    def zero_init_steps(cls, fname: str) -> tuple[float, ...]:
        """Return additive seed values (µs) tried when a field is at 0."""
        if cls.ZERO_INIT_STEPS and fname in cls.ZERO_INIT_STEPS:
            return cls.ZERO_INIT_STEPS[fname]
        if fname.startswith("k_"):
            return ()
        return (0.5, 2.0, 5.0)

    @classmethod
    def is_cpu_bound(cls, fname: str) -> bool:
        """Whether *fname* should be rescaled when porting to a new CPU clock."""
        return fname in cls.CPU_BOUND_FIELDS


# ------------------------------------------------------------------
# Concrete metadata tables (populated AFTER the dataclass body).
# Kept module-level so they can be patched in tests if needed.
# ------------------------------------------------------------------

#: Plausible physical bounds in microseconds (or unitless for ``k_*``).
#: Anything outside this box is rejected by the fitter as non-physical.
_COST_BOUNDS: Dict[str, tuple[float, float]] = {
    # Fixed overhead and timer reads
    "t_main_fixed":              (1.0, 40.0),
    "t_gpt_read":                (0.1, 12.0),

    # ClcMainTranB1
    "t_b1_per_entry":            (0.5, 12.0),

    # Async path
    "t_async_recurrence":        (0.0, 30.0),
    "t_l1a_per_event_new":       (1.0, 30.0),
    "t_l1a_per_event_displace":  (1.0, 40.0),
    "t_resort_per_entry":        (0.0, 5.0),

    # L1b scan (per NrFmy entry)
    "t_l1b_per_entry_empty":     (0.05, 3.0),
    "t_l1b_per_entry_valid":     (0.1,  8.0),
    "t_l1b_resorting":           (0.0,  8.0),

    "t_lamp":                    (0.05, 5.0),

    # Main2 / StoreFRF
    "t_main2_recurrence":        (0.0, 30.0),
    "t_deferred_base":           (1.0, 30.0),
    "t_storefrf_no_update":      (0.05, 8.0),
    "t_storefrf_free_frame":     (0.05, 6.0),
    "t_storefrf_full_shift":     (0.5, 15.0),

    # Collect helpers
    "t_collect_per_idx":         (0.0, 0.5),
    "t_collect_fixed":           (0.0, 8.0),
    "t_collect_per_entry":       (0.0, 5.0),

    # FrfPre / NVM / FctPerm
    "t_frfpre_per_entry":        (0.0, 6.0),
    "t_nvm_onfly":               (0.0, 2.0),
    "t_frfsrv":                  (0.0, 5.0),
    "t_fct_perm":                (0.0, 8.0),
    "t_fct_scdn":                (0.0, 5.0),
    "t_upd_obd_frf":             (0.0, 3.0),

    # Topology / runtime overheads
    "t_client_per_client":       (0.0, 25.0),
    "t_event_db_per_event":      (0.0, 0.6),
    "t_core_sync_per_peer":      (0.0, 25.0),
    "t_shared_core_penalty":     (0.0, 80.0),
    "t_ptu_profile_penalty":     (0.0, 10.0),

    # Worst-case ISR / prio swap / cache
    "t_isr_jitter":              (0.0, 200.0),
    "t_prio_swap":               (0.0, 500.0),
    "t_cache_miss_per_block":    (0.0, 30.0),

    # Scaling factors
    "k_scenario2_variable":      (0.3, 1.2),
    "k_proj":                    (0.5, 1.8),
}

#: Costs that scale ~linearly with the CPU clock (pure ALU work).  All
#: other tunable fields are memory / IO / IRQ bound and stay constant
#: when porting to a different CPU frequency.
_CPU_BOUND_FIELDS: frozenset[str] = frozenset({
    "t_main_fixed",
    "t_gpt_read",
    "t_b1_per_entry",
    "t_l1a_per_event_new",
    "t_l1a_per_event_displace",
    "t_resort_per_entry",
    "t_l1b_per_entry_empty",
    "t_l1b_per_entry_valid",
    "t_l1b_resorting",
    "t_lamp",
    "t_deferred_base",
    "t_async_recurrence",
    "t_main2_recurrence",
    "t_fct_perm",
    "t_fct_scdn",
})

#: Additive seed values (µs) tried when a tunable field is currently 0.
#: Without these, the multiplicative descent (``val * (1+δ)``) cannot
#: ever lift a field above 0 — fields such as ``t_isr_jitter`` and
#: ``t_prio_swap`` stay permanently disabled.
_ZERO_INIT_STEPS: Dict[str, tuple[float, ...]] = {
    "t_isr_jitter":            (20.0, 60.0, 120.0),
    "t_prio_swap":             (50.0, 150.0, 300.0),
    "t_cache_miss_per_block":  (2.0, 5.0, 10.0),
    "t_shared_core_penalty":   (10.0, 30.0, 60.0),
    "t_core_sync_per_peer":    (2.0, 8.0, 15.0),
    "t_client_per_client":     (1.0, 5.0, 12.0),
    "t_event_db_per_event":    (0.02, 0.1, 0.3),
    "t_ptu_profile_penalty":   (1.0, 3.0, 6.0),
    "t_async_recurrence":      (1.0, 5.0, 12.0),
    "t_main2_recurrence":      (1.0, 5.0, 12.0),
    "t_collect_per_entry":     (0.2, 1.0, 3.0),
}

# Attach to the dataclass so they are accessible via ``MicroCosts.BOUNDS`` etc.
MicroCosts.BOUNDS = _COST_BOUNDS
MicroCosts.CPU_BOUND_FIELDS = _CPU_BOUND_FIELDS
MicroCosts.ZERO_INIT_STEPS = _ZERO_INIT_STEPS


# ==============================================================================
# Baseline costs for known projects (offline fallback + transfer-learning seed)
#
# In production the bench_store is checked FIRST (see get_project_costs).
# These hardcoded sets are used when:
#   1. bench_store is not available (new machine, CI, offline).
#   2. transfer_fit needs a structural reference to seed coordinate-descent.
#   3. selftest / smoke-test runs that must work without external files.
#
# COSTS_PROJ1 / COSTS_PROJ2 / COSTS_PROJ3 — LEGACY SEEDS
#   Calibrated with fewer parameters (no t_gpt_read, k_proj etc.).
#   Used ONLY as transfer-learning starting points and for excel_report comparison.
#   PROJECT_COSTS maps PROJ1/PROJ3 to the fully-fitted specific variants below.
# ==============================================================================

COSTS_PROJ2 = MicroCosts(
    t_main_fixed=7.552,
    t_async_recurrence=0.0,
    t_b1_per_entry=2.5,
    t_l1a_per_event_new=7.159,
    t_l1a_per_event_displace=10.595,
    t_l1b_per_entry_empty=0.832,
    t_l1b_per_entry_valid=0.879,
    t_l1b_resorting=0.023,
    t_lamp=0.286,
    t_main2_recurrence=0.0,
    t_deferred_base=7.197,
    t_storefrf_no_update=1.512,
    t_storefrf_free_frame=1.723,
    t_storefrf_full_shift=4.802,
    t_collect_per_idx=0.001,
    t_collect_fixed=0.026,
    t_frfpre_per_entry=0.8,
    t_nvm_onfly=0.019,
    t_frfsrv=0.0,
    t_fct_perm=0.003,
    t_fct_scdn=0.002,
    t_upd_obd_frf=0.001,
    k_scenario2_variable=1.0,
)

COSTS_PROJ3 = MicroCosts(
    t_main_fixed=1.825,
    t_async_recurrence=0.0,
    t_b1_per_entry=3.5,
    t_l1a_per_event_new=6.197,
    t_l1a_per_event_displace=14.775,
    t_l1b_per_entry_empty=0.3,
    t_l1b_per_entry_valid=0.491,
    t_l1b_resorting=0.058,
    t_lamp=1.040,
    t_main2_recurrence=0.0,
    t_deferred_base=15.618,
    t_storefrf_no_update=5.520,
    t_storefrf_free_frame=0.186,
    t_storefrf_full_shift=8.327,
    t_collect_per_idx=0.017,
    t_collect_fixed=2.316,
    t_frfpre_per_entry=1.0,
    t_nvm_onfly=0.096,
    t_frfsrv=0.0,
    t_fct_perm=0.143,
    t_fct_scdn=0.077,
    t_upd_obd_frf=0.037,
    k_scenario2_variable=1.0,
)

COSTS_PROJ1 = MicroCosts(
    t_main_fixed=1.995,
    t_async_recurrence=0.0,
    t_b1_per_entry=3.0,
    t_l1a_per_event_new=13.289,
    t_l1a_per_event_displace=14.334,
    t_l1b_per_entry_empty=0.033,
    t_l1b_per_entry_valid=0.082,
    t_l1b_resorting=0.422,
    t_lamp=0.116,
    t_main2_recurrence=0.0,
    t_deferred_base=5.312,
    t_storefrf_no_update=0.1,
    t_storefrf_free_frame=2.437,
    t_storefrf_full_shift=8.217,
    t_collect_per_idx=0.012,
    t_collect_fixed=0.074,
    t_frfpre_per_entry=1.0,
    t_nvm_onfly=0.143,
    t_frfsrv=0.0,
    t_fct_perm=0.109,
    t_fct_scdn=0.055,
    t_upd_obd_frf=0.074,
    k_scenario2_variable=1.0,
)

COSTS_PROJ5_000U0 = MicroCosts(
    t_main_fixed=17.9217,
    t_gpt_read=7.4906,
    t_b1_per_entry=2.5,
    t_async_recurrence=0.0,
    t_l1a_per_event_new=10.4146,
    t_l1a_per_event_displace=10.5182,
    t_resort_per_entry=0.0,
    t_l1b_per_entry_empty=0.832,
    t_l1b_per_entry_valid=3.6428,
    t_l1b_resorting=0.0026,
    t_lamp=1.0972,
    t_main2_recurrence=0.0,
    t_deferred_base=8.4569,
    t_storefrf_no_update=1.5410,
    t_storefrf_free_frame=0.6226,
    t_storefrf_full_shift=1.8464,
    t_collect_per_idx=0.0016,
    t_collect_fixed=0.1116,
    t_collect_per_entry=0.8868,
    t_frfpre_per_entry=0.8,
    t_nvm_onfly=0.0151,
    t_frfsrv=0.0,
    t_fct_perm=0.0666,
    t_fct_scdn=0.0444,
    t_upd_obd_frf=0.0222,
    t_client_per_client=12.0,
    t_event_db_per_event=0.18,
    t_core_sync_per_peer=9.0,
    t_shared_core_penalty=30.0,
    t_ptu_profile_penalty=3.0,
    k_scenario2_variable=0.8912,
    k_proj=1.2,
)

COSTS_PROJ1_0U0_OB6_023 = MicroCosts(
    t_main_fixed=0.0402,
    t_gpt_read=5.7093,
    t_b1_per_entry=3.5,
    t_async_recurrence=0.0,
    t_l1a_per_event_new=14.0315,
    t_l1a_per_event_displace=13.7215,
    t_resort_per_entry=0.0,
    t_l1b_per_entry_empty=0.3,
    t_l1b_per_entry_valid=0.0185,
    t_l1b_resorting=0.0190,
    t_lamp=0.0191,
    t_main2_recurrence=0.0,
    t_deferred_base=11.8697,
    t_storefrf_no_update=5.4206,
    t_storefrf_free_frame=0.0307,
    t_storefrf_full_shift=0.3394,
    t_collect_per_idx=0.0056,
    t_collect_fixed=3.5553,
    t_collect_per_entry=0.2863,
    t_frfpre_per_entry=1.0,
    t_nvm_onfly=0.0029,
    t_frfsrv=0.0,
    t_fct_perm=5.1398,
    t_fct_scdn=1.5954,
    t_upd_obd_frf=0.1687,
    k_scenario2_variable=0.6858,
    k_proj=0.8486,
)

COSTS_PROJ3_0U0_P16_624 = MicroCosts(
    t_main_fixed=4.9900,
    t_gpt_read=3.9881,
    t_b1_per_entry=3.5,
    t_async_recurrence=0.0,
    t_l1a_per_event_new=10.0495,
    t_l1a_per_event_displace=11.1695,
    t_resort_per_entry=0.0,
    t_l1b_per_entry_empty=0.3,
    t_l1b_per_entry_valid=0.0215,
    t_l1b_resorting=0.0003,
    t_lamp=1.7359,
    t_main2_recurrence=0.0,
    t_deferred_base=18.8587,
    t_storefrf_no_update=4.2049,
    t_storefrf_free_frame=0.6516,
    t_storefrf_full_shift=1.4618,
    t_collect_per_idx=0.0179,
    t_collect_fixed=5.1756,
    t_collect_per_entry=0.4319,
    t_frfpre_per_entry=1.0,
    t_nvm_onfly=0.2312,
    t_frfsrv=0.0,
    t_fct_perm=2.8069,
    t_fct_scdn=1.3494,
    t_upd_obd_frf=1.0894,
    k_scenario2_variable=0.4159,
    k_proj=1.0229,
)

# ==============================================================================
# PROJ4_0U0_000  —  ECU platform X, TC39x, core A1 (5 ms task, shared)
#
# Seeded from RuntimeMeasureReduction.xlsx / Tabelle2 bench measurements:
#   NrFmy=36, NrClcFmyEveAsyn=20, NrClcFmyPost=10  (Calibration 1)
#   Worst-case (Scenario 1) bench values:
#     wout_int / wout_prio:  670 µs   (pure CPU baseline)
#     with_int / wout_prio:  780 µs   (+110 µs ISR)
#     wout_int / with_prio: 1000 µs   (+330 µs OBD/UDS prio swap)
#     with_int / with_prio: 1200 µs   (+530 µs combined)
#   t_isr_jitter seeded at Cal1 ISR delta = 110 µs.
#   t_prio_swap seeded at Cal1 prio delta = 330 µs.
#   k_proj tuned so simulated total ≈ bench "wout_int / wout_prio" baseline.
#   Run --mode fit with bench data to refine all t_* fields.
# ==============================================================================
COSTS_PROJ4_0U0_000 = MicroCosts(
    # Fixed overhead: Gpt_ConvertTicksToMicrosec (called twice) + config check
    t_main_fixed=12.0,
    t_gpt_read=6.0,
    t_b1_per_entry=3.0,
    t_async_recurrence=10.0,
    # L1a: new entry vs displacement (displacement heavier due to HistoryResorting)
    t_l1a_per_event_new=9.0,
    t_l1a_per_event_displace=13.0,
    t_resort_per_entry=0.0,
    # L1b: iterates ALL NrFmy=36 entries every call
    t_l1b_per_entry_empty=0.5,
    t_l1b_per_entry_valid=1.2,
    t_l1b_resorting=0.1,
    t_lamp=1.0,
    # Main2 / StoreFrf: deferred FRF processing
    t_main2_recurrence=8.0,
    t_deferred_base=10.0,
    t_storefrf_no_update=2.0,
    t_storefrf_free_frame=1.5,
    t_storefrf_full_shift=4.5,
    t_collect_per_idx=0.01,
    t_collect_fixed=0.5,
    t_collect_per_entry=0.5,
    p_frfpre_hit=0.0,           # worst-case: no prestored FRF hit in WCS scenarios
    t_frfpre_per_entry=1.0,
    t_nvm_onfly=0.5,
    t_frfsrv=0.0,
    t_fct_perm=2.0,
    t_fct_scdn=1.0,
    t_upd_obd_frf=0.3,
    # New terms — calibrated from Tabelle2
    t_isr_jitter=110.0,         # ISR preemption overhead (Tabelle2 Cal1, wout prio: 780-670)
    t_prio_swap=330.0,          # OBD/UDS prio overhead (Tabelle2 Cal1, wout int: 1000-670)
    t_cache_miss_per_block=5.0, # cold-cache per FRF block (PFLASH first-touch)
    # Topology — A1 core is shared with other BSW/ASW tasks on PROJ4
    t_client_per_client=5.0,
    t_event_db_per_event=0.1,
    t_core_sync_per_peer=5.0,
    t_shared_core_penalty=30.0,
    t_ptu_profile_penalty=2.0,
    k_scenario2_variable=0.85,
    k_proj=1.0,
)

# Map project name -> fitted costs
# NOTE: Generic keys (PROJ1, PROJ3) point to the best fully-fitted variant.
#       COSTS_PROJ1 / COSTS_PROJ2 / COSTS_PROJ3 legacy objects are kept as
#       transfer-learning seeds and for excel_report cost comparison only.
PROJECT_COSTS: Dict[str, MicroCosts] = {
    # Generic prefix fallbacks — point to fully-fitted specific variants
    "PROJ1": COSTS_PROJ1_0U0_OB6_023,
    "PROJ2": COSTS_PROJ2,               # no specific variant yet, legacy stays
    "PROJ3": COSTS_PROJ3_0U0_P16_624,
    "PROJ4": COSTS_PROJ4_0U0_000,
    # Fully-fitted specific variants
    "PROJ5_000U0": COSTS_PROJ5_000U0,
    "PROJ1_0U0_OB6_023": COSTS_PROJ1_0U0_OB6_023,
    "PROJ3_0U0_P16_624": COSTS_PROJ3_0U0_P16_624,
    "PROJ4_0U0_000": COSTS_PROJ4_0U0_000,
}


def get_project_costs(
    project_name: str,
    cfg: "Optional[Any]" = None,
) -> MicroCosts:
    """Return calibrated costs for a project.

    Search order:
    1. Check the centralized bench store (fitted costs from real bench data).
    2. Check the exact key in ``PROJECT_COSTS`` (hardcoded in code).
    3. Check the first 5 characters / first token in ``PROJECT_COSTS``.
    4. Use transfer learning enriched with **all** configurations and costs
       from the bench store (not just PROJ2/PROJ3).
    5. Fall back to ``MicroCosts()`` with a warning.

    Parameters
    ----------
    project_name : str
        Project name (e.g. ``"PROJ6_0U0_000"`` or ``"PROJ3"``).
    cfg : ProjectConfig, optional
        Project configuration. If provided, transfer learning is enabled.

    Returns
    -------
    MicroCosts
        Calibrated costs, estimated by transfer, or defaults.
    """
    # --- 1. Check centralized bench store (highest priority) ----------------
    stored_costs: Optional[MicroCosts] = None
    try:
        from dem_simulator.bench_store import _ensure_seeded, get_fitted_costs
        _ensure_seeded()
        stored_costs = get_fitted_costs(project_name)
        if stored_costs is not None:
            _log.info(
                "[%s] Loaded fitted costs from bench store.", project_name,
            )
            return stored_costs
    except Exception as exc:
        _log.debug("[%s] Bench store lookup failed: %s", project_name, exc)

    # --- 2-3. Check in-memory PROJECT_COSTS (hardcoded) ---------------------
    key = project_name.upper()
    if key in PROJECT_COSTS:
        return PROJECT_COSTS[key]
    short = key[:5] if len(key) >= 5 else key
    if short in PROJECT_COSTS:
        return PROJECT_COSTS[short]
    prefix = key.split("_")[0]
    if prefix in PROJECT_COSTS:
        return PROJECT_COSTS[prefix]

    # Transfer learning if we have ProjectConfig
    if cfg is not None:
        try:
            from dem_simulator.transfer_fit import infer_costs_for_project
            _log.info(
                "[%s] No calibrated costs and ProjectConfig provided. "
                "Estimating costs using transfer learning.",
                project_name,
            )
            estimated = infer_costs_for_project(cfg)
            return estimated
        except Exception as exc:
            _log.warning(
                "[%s] Transfer learning failed (%s) — falling back to MicroCosts().",
                project_name, exc,
            )

    _log.warning(
        "[%s] No calibrated costs are available and no ProjectConfig was provided.\n"
        "  → Using default MicroCosts() values (rough estimate).\n"
        "  → For better precision: provide cfg= or run transfer_fit() with bench data.",
        project_name,
    )
    return MicroCosts()
