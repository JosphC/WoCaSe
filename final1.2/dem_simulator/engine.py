"""Core simulation engine: DemMainFunctionSimulator.

Models the execution of ``Icsp_Dem_MainFunction`` step by step,
accumulating microseconds for each sub-function called between
the two ``Iopt_Gpt_GetSystemTime()`` samples.
"""

from __future__ import annotations

from typing import Dict

from dem_simulator.exceptions import SimulatorError, ConfigValidationError
from dem_simulator.constants import (
    BYTE_COPY_COST_US,
    NVM_WRITE_COST_US,
    TEST_FRF_DATA_COST_US,
    WAIT_CLR_RESP_COST_US,
)
from dem_simulator.config import ProjectConfig, FrfBlockConfig
from dem_simulator.costs import MicroCosts
from dem_simulator.scenarios import Scenario


class DemMainFunctionSimulator:
    """Models the execution of ``Icsp_Dem_MainFunction`` step by step.

    Accumulates microseconds for each sub-function called between the
    two ``Iopt_Gpt_GetSystemTime()`` samples.

    The model covers:

    * Worst-recurrence logic (Scenario 1: 2nd recurrence = all displacements)
    * Per-block FRF geometry (4 blocks with different sizes / depths)
    * Separate new-entry vs displacement L1a cost
    * Per-entry deferred ``StoreFrf`` with free-frame vs full-frame-shift logic
    """

    def __init__(self, cfg: ProjectConfig, costs: MicroCosts) -> None:
        if cfg is None:
            raise SimulatorError("ProjectConfig must not be None")
        if costs is None:
            raise SimulatorError("MicroCosts must not be None")
        self.cfg = cfg
        self.c = costs

    # -- helpers --

    def _storefrf_cost_per_block(
        self,
        blk: FrfBlockConfig,
        frf_full: bool,
    ) -> float:
        """Cost of StoreFrf for one FRF block for one deferred entry.

        Parameters
        ----------
        blk : FrfBlockConfig
            The FRF block configuration.
        frf_full : bool
            Whether all FRF frame slots are occupied.
        The collect cost is weighted by ``(1 - p_frfpre_hit)`` so that
        projects with high FrfPre hit rate avoid redundant collect work.
        """
        cost = 0.0
        collect_factor = max(0.0, min(1.0, 1.0 - self.c.p_frfpre_hit))
        collect_cost = collect_factor * (
            self.c.t_collect_fixed
            + self.c.t_collect_per_entry
            + blk.NrIdxPerClass * self.c.t_collect_per_idx
        )

        if not frf_full:
            # Free frame available -> copy prestored or collect
            cost += self.c.t_storefrf_free_frame
            cost += collect_cost
        else:
            # All frames full -> shift + rewrite
            shiftable = blk.NrFrfTot - blk.NrFrfHold
            if shiftable > 0:
                # Byte-copy: (shiftable-1) frames shifted + 1 frame written
                shift_bytes = max(0, (shiftable - 1)) * blk.NrByteFrame
                cost += self.c.t_storefrf_full_shift
                cost += shift_bytes * BYTE_COPY_COST_US
                cost += collect_cost
            else:
                cost += self.c.t_storefrf_no_update
        return cost

    def _storefrf_cost(self, frf_full: bool) -> float:
        """Total StoreFrf cost across all blocks for one deferred entry."""
        return sum(
            self._storefrf_cost_per_block(blk, frf_full)
            for blk in self.cfg.FrfBlocks
        )

    # -- main simulation --

    def simulate(self, scenario: Scenario,
                 NrClcFmyEveAsyn: int,
                 NrClcFmyPost: int) -> Dict[str, float]:
        """Simulate one call of ``Icsp_Dem_MainFunction``.

        Returns a breakdown dict ``{ phase_name: microseconds }``.

        Parameters
        ----------
        scenario : Scenario
            The worst-case scenario to simulate.
        NrClcFmyEveAsyn : int
            Maximum events processed per recurrence (calibratable).
        NrClcFmyPost : int
            Maximum deferred entries processed per recurrence (calibratable).

        Raises
        ------
        ConfigValidationError
            If calibration values are non-positive.
        """
        if NrClcFmyEveAsyn <= 0:
            raise ConfigValidationError(
                f"NrClcFmyEveAsyn must be > 0, got {NrClcFmyEveAsyn}"
            )
        if NrClcFmyPost <= 0:
            raise ConfigValidationError(
                f"NrClcFmyPost must be > 0, got {NrClcFmyPost}"
            )
        breakdown = {}
        c = self.c
        cfg = self.cfg
        # Scenario where only new entries are inserted (no displacement, FMY not pre-filled).
        # This corresponds to Scenario 1 (first recurrence, empty FMY slots available).
        # k_scenario2_variable was historically misnamed; it scales this lighter scenario.
        is_scenario1_only = scenario.nr_events_second == 0 and not scenario.fmy_initially_full
        variable_factor = c.k_scenario2_variable if is_scenario1_only else 1.0

        # ─── Fixed overhead ───────────────────────────────────────────────────
        breakdown["fixed_overhead"] = c.t_main_fixed + 2.0 * c.t_gpt_read

        # ─── Generic topology/runtime overheads ───────────────────────────────
        # WCS scenarios inject the maximum number of events (nr_inject_first +
        # nr_inject_next ≥ NrFmy) so all DEM tables and callbacks are fully
        # exercised.  Use activity=1.0 unconditionally — any lower value would
        # artificially suppress EventDbScan/ClientCallbacks in the worst case.
        activity = 1.0

        breakdown["EventDbScan"] = cfg.NrEve * c.t_event_db_per_event * activity
        breakdown["ClientCallbacks"] = (
            cfg.NrClient * c.t_client_per_client * (0.5 + 0.5 * activity)
        )
        breakdown["CoreSync"] = (
            max(0, cfg.NrCore - 1) * c.t_core_sync_per_peer
            + (c.t_shared_core_penalty if cfg.IsSharedCore else 0.0)
        )
        breakdown["PtuProfileSwitch"] = max(0, cfg.NrPtuProfiles - 1) * c.t_ptu_profile_penalty

        # ─── ISR preemption jitter ────────────────────────────────────────────
        # Hard interrupts (CAN, GPT, ADC) that fire between the two
        # Gpt_GetSystemTime() samples inflate wall-clock time on bench.
        # t_isr_jitter is calibrated from Tabelle2 col "with_int" − "wout_int".
        breakdown["IsrJitter"] = c.t_isr_jitter

        # ─── OBD/UDS priority-swap overhead ──────────────────────────────────
        # When OBD-on-UDS prio swap is active, Icsp_Dem_Prio evaluates an
        # additional priority table in every MainFunction call.
        # Calibrated from Tabelle2 col "wout_int/with_prio" − "wout_int/wout_prio".
        breakdown["PrioSwap"] = c.t_prio_swap if cfg.has_prio_obd_uds_swap else 0.0

        # ─── Cold-cache penalty (FRF block first-touch) ───────────────────────
        # PFLASH/PSPR first-touch misses when FRF blocks are accessed.
        # Only relevant for the measured worst-case recurrence in WCS.
        breakdown["CacheWarmup"] = cfg.NrBlockFrf * c.t_cache_miss_per_block

        # ─── ClcMainTran  (called with ArgLvClcAll=FALSE) ─────────────────────

        # -- B1: confirmed threshold entries from MEPA queue --
        # In worst case scenarios, B1 entries are 0 (events come via FIFO)
        nr_b1 = 0
        budget = NrClcFmyEveAsyn
        async_active = (scenario.nr_events_first + scenario.nr_events_second + nr_b1) > 0
        breakdown["AsyncSetup"] = c.t_async_recurrence if async_active else 0.0
        breakdown["B1_mepa"] = variable_factor * (nr_b1 * c.t_b1_per_entry)
        budget -= nr_b1

        # -- L1a: FIFO events --
        # Model the WORST single recurrence.
        # For Scenario 1 (40 events, budget 20):
        #   Rec 1 processes 20 events: 20 fill empty slots (cheap)
        #   Rec 2 processes 20 events: 20 displacements (expensive) <- worst
        # For Scenario 3 (20 events, FMY full, budget 20):
        #   Rec 1 processes 20 events: all 20 are displacements <- worst
        nr_events_total = scenario.nr_events_first + scenario.nr_events_second

        if scenario.fmy_initially_full:
            nr_l1a = min(nr_events_total, budget)
            nr_displace = nr_l1a
            nr_new = 0
        elif scenario.nr_events_second <= 0:
            nr_l1a = min(scenario.nr_events_first, budget, cfg.NrFmy)
            nr_displace = 0
            nr_new = nr_l1a
        else:
            # Two-batch WCS: compare first and second recurrence costs and keep
            # the heavier one as the measured worst recurrence.
            first_rec = min(scenario.nr_events_first, budget, cfg.NrFmy)
            free_after_first = max(0, cfg.NrFmy - first_rec)

            second_processed = min(scenario.nr_events_second, budget)
            second_new = min(second_processed, free_after_first)
            second_displace = max(0, second_processed - second_new)

            first_cost = first_rec * c.t_l1a_per_event_new
            second_cost = (
                second_new * c.t_l1a_per_event_new
                + second_displace * c.t_l1a_per_event_displace
            )

            if second_cost >= first_cost:
                nr_l1a = second_processed
                nr_new = second_new
                nr_displace = second_displace
            else:
                nr_l1a = first_rec
                nr_new = first_rec
                nr_displace = 0

        t_l1a = (nr_new * c.t_l1a_per_event_new +
                 nr_displace * c.t_l1a_per_event_displace)
        breakdown["L1a_fifo"] = variable_factor * t_l1a

        # -- L1b: scan all NrFmy entries --
        if scenario.fmy_initially_full or nr_events_total >= cfg.NrFmy:
            nr_valid = cfg.NrFmy
        else:
            nr_valid = min(nr_events_total, cfg.NrFmy)
        nr_empty = cfg.NrFmy - nr_valid

        t_l1b = (nr_valid * c.t_l1b_per_entry_valid +
                 nr_empty * c.t_l1b_per_entry_empty)
        # If entries were erased/displaced, resorting is triggered
        if nr_displace > 0:
            t_l1b += c.t_l1b_resorting
            t_l1b += cfg.NrFmy * c.t_resort_per_entry
        breakdown["L1b_scan"] = variable_factor * t_l1b

        # -- Lamp: 1 entry --
        breakdown["Lamp"] = c.t_lamp

        # ─── FctScdn.PtrFctClcMain() ──────────────────────────────────────────
        breakdown["FctScdn"] = c.t_fct_scdn

        # ─── ClcMain2  (called with ArgLvClcAll=FALSE) ────────────────────────

        # Number of entries queued for deferred processing
        nr_deferred_queued = nr_l1a + nr_b1
        nr_deferred = min(nr_deferred_queued, NrClcFmyPost)

        # For scenarios with displacement, FRF slots are typically full
        frf_full = scenario.frf_slots_full or (nr_displace > 0)

        breakdown["Main2_Setup"] = c.t_main2_recurrence if (nr_deferred_queued > 0 or cfg.NrFrfPre > 0) else 0.0
        t_main2_frf = 0.0
        for _i in range(nr_deferred):
            t_main2_frf += c.t_deferred_base
            t_main2_frf += self._storefrf_cost(frf_full)
        breakdown["Main2_FrfUpd"] = variable_factor * t_main2_frf if is_scenario1_only else t_main2_frf

        # Remaining budget for FrfPre
        remaining_budget = NrClcFmyPost - nr_deferred
        nr_frfpre = min(remaining_budget, cfg.NrFrfPre) if remaining_budget > 0 else 0
        t_frfpre = nr_frfpre * c.t_frfpre_per_entry
        breakdown["Main2_FrfPre"] = variable_factor * t_frfpre if is_scenario1_only else t_frfpre

        # NVM on-fly
        breakdown["Main2_NvmOnFly"] = c.t_nvm_onfly

        # UpdObdFrf
        breakdown["Main2_UpdObdFrf"] = c.t_upd_obd_frf

        # ─── FrfSrv_GetFrfData ────────────────────────────────────────────────
        breakdown["FrfSrv"] = c.t_frfsrv

        # ─── FctPerm.PtrFctClcMainFunction ────────────────────────────────────
        breakdown["FctPerm"] = c.t_fct_perm

        # --- NVM write ---
        breakdown["NvmWr"] = cfg.NrFmyBufNvmWr * NVM_WRITE_COST_US

        # --- Frf_TestFrfData  (O(1) per call) ---
        breakdown["TestFrfData"] = TEST_FRF_DATA_COST_US

        # --- WaitClrResp ---
        breakdown["WaitClrResp"] = WAIT_CLR_RESP_COST_US

        return breakdown

    def simulate_total(self, scenario: Scenario,
                       NrClcFmyEveAsyn: int,
                       NrClcFmyPost: int) -> float:
        """Return total simulated microseconds for one scenario + calibration."""
        total = sum(self.simulate(scenario, NrClcFmyEveAsyn, NrClcFmyPost).values())
        return total * self.c.k_proj