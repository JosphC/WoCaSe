"""Seed data for the centralized bench store.

This module contains declarative reference projects used to populate an empty
SQLite bench store on first run. Runtime logic can then query the database as
the primary source of truth while still keeping code paths deterministic and
versioned.
"""

from __future__ import annotations

from typing import Any, Dict, List


SEED_ENTRIES: List[Dict[str, Any]] = [
    {
        "project_name": "PROJ2",
        "source": "Bench measurement Schaeffler ERRM lab, TC387 @ 300 MHz",
        "fit_rmse": 4.2,
        "calibrations": [(20, 10), (10, 10), (10, 5), (5, 5), (5, 4), (5, 3)],
        "bench": {
            "scenario_1": [727, 601, 506, 399, 381, 362],
            "scenario_2": [456, 380, 316, 249, 237, 225],
            "scenario_3": [668, 594, 471, 356, 338, 320],
        },
        "cfg_kwargs": {
            "name": "PROJ2",
            "NrFmy": 12, "NrFifoBas": 4, "NrFifoIntm": 8, "NrFifoRsv": 0,
            "NrClcFmyEveAsyn": 20, "NrClcFmyPost": 10, "NrEve": 150,
            "NrFrfDataTot": 48, "NrFrfPreData": 0, "NrBlockFrf": 4,
            "NrFrfPre": 6, "NrByteFrfFmy": 48, "NrLamp": 2,
            "cpu_clock_mhz": 300.0,
            "FrfBlocks": [
                {"NrByteFrame": 48, "NrFrfIdxCalMax": 6, "NrIdxPerClass": 6, "NrFrfHold": 2, "NrFrfTot": 8, "LfOptions": 0},
                {"NrByteFrame": 32, "NrFrfIdxCalMax": 4, "NrIdxPerClass": 4, "NrFrfHold": 2, "NrFrfTot": 6, "LfOptions": 0},
                {"NrByteFrame": 24, "NrFrfIdxCalMax": 3, "NrIdxPerClass": 3, "NrFrfHold": 1, "NrFrfTot": 4, "LfOptions": 0},
                {"NrByteFrame": 16, "NrFrfIdxCalMax": 2, "NrIdxPerClass": 2, "NrFrfHold": 1, "NrFrfTot": 3, "LfOptions": 0},
            ],
        },
        "cost_kwargs": {
            "t_main_fixed": 7.552, "t_async_recurrence": 0.0,
            "t_b1_per_entry": 2.5,
            "t_l1a_per_event_new": 7.159, "t_l1a_per_event_displace": 10.595,
            "t_l1b_per_entry_empty": 0.832, "t_l1b_per_entry_valid": 0.879,
            "t_l1b_resorting": 0.023, "t_lamp": 0.286,
            "t_main2_recurrence": 0.0, "t_deferred_base": 7.197,
            "t_storefrf_no_update": 1.512, "t_storefrf_free_frame": 1.723,
            "t_storefrf_full_shift": 4.802, "t_collect_per_idx": 0.001,
            "t_collect_fixed": 0.026, "t_frfpre_per_entry": 0.8,
            "t_nvm_onfly": 0.019, "t_frfsrv": 0.0,
            "t_fct_perm": 0.003, "t_fct_scdn": 0.002,
            "t_upd_obd_frf": 0.001, "k_scenario2_variable": 1.0,
        },
    },
    {
        "project_name": "PROJ1_0U0_OB6_023",
        "source": "Bench measurement Schaeffler ERRM lab, TC387 @ 300 MHz",
        "fit_rmse": 5.1,
        "calibrations": [(20, 10), (10, 10), (10, 5), (5, 5), (5, 4), (5, 3)],
        "bench": {
            "scenario_1": [698, 572, 481, 376, 358, 340],
            "scenario_2": [431, 358, 296, 232, 221, 209],
            "scenario_3": [634, 563, 445, 334, 317, 300],
        },
        "cfg_kwargs": {
            "name": "PROJ1_0U0_OB6_023",
            "NrFmy": 12, "NrFifoBas": 4, "NrFifoIntm": 8, "NrFifoRsv": 0,
            "NrClcFmyEveAsyn": 20, "NrClcFmyPost": 10, "NrEve": 150,
            "NrFrfDataTot": 48, "NrFrfPreData": 0, "NrBlockFrf": 4,
            "NrFrfPre": 6, "NrByteFrfFmy": 48, "NrLamp": 2,
            "cpu_clock_mhz": 300.0,
            "FrfBlocks": [
                {"NrByteFrame": 48, "NrFrfIdxCalMax": 6, "NrIdxPerClass": 6, "NrFrfHold": 2, "NrFrfTot": 8, "LfOptions": 0},
                {"NrByteFrame": 32, "NrFrfIdxCalMax": 4, "NrIdxPerClass": 4, "NrFrfHold": 2, "NrFrfTot": 6, "LfOptions": 0},
                {"NrByteFrame": 24, "NrFrfIdxCalMax": 3, "NrIdxPerClass": 3, "NrFrfHold": 1, "NrFrfTot": 4, "LfOptions": 0},
                {"NrByteFrame": 16, "NrFrfIdxCalMax": 2, "NrIdxPerClass": 2, "NrFrfHold": 1, "NrFrfTot": 3, "LfOptions": 0},
            ],
        },
        "cost_kwargs": {
            "t_main_fixed": 0.0402, "t_gpt_read": 5.7093,
            "t_b1_per_entry": 3.5, "t_async_recurrence": 0.0,
            "t_l1a_per_event_new": 14.0315, "t_l1a_per_event_displace": 13.7215,
            "t_resort_per_entry": 0.0,
            "t_l1b_per_entry_empty": 0.3, "t_l1b_per_entry_valid": 0.0185,
            "t_l1b_resorting": 0.0190, "t_lamp": 0.0191,
            "t_main2_recurrence": 0.0, "t_deferred_base": 11.8697,
            "t_storefrf_no_update": 5.4206, "t_storefrf_free_frame": 0.0307,
            "t_storefrf_full_shift": 0.3394, "t_collect_per_idx": 0.0056,
            "t_collect_fixed": 3.5553, "t_collect_per_entry": 0.2863,
            "t_frfpre_per_entry": 1.0, "t_nvm_onfly": 0.0029,
            "t_frfsrv": 0.0, "t_fct_perm": 5.1398, "t_fct_scdn": 1.5954,
            "t_upd_obd_frf": 0.1687, "k_scenario2_variable": 0.6858,
            "k_proj": 0.8486,
        },
    },
    {
        "project_name": "PROJ3_0U0_P16_624",
        "source": "Bench measurement Schaeffler ERRM lab, TC387 @ 300 MHz",
        "fit_rmse": 3.8,
        "calibrations": [(20, 10), (10, 10), (10, 5), (5, 5), (5, 4), (5, 3)],
        "bench": {
            "scenario_1": [812, 668, 561, 441, 420, 399],
            "scenario_2": [509, 424, 352, 277, 264, 251],
            "scenario_3": [745, 663, 526, 397, 377, 358],
        },
        "cfg_kwargs": {
            "name": "PROJ3_0U0_P16_624",
            "NrFmy": 12, "NrFifoBas": 4, "NrFifoIntm": 8, "NrFifoRsv": 0,
            "NrClcFmyEveAsyn": 20, "NrClcFmyPost": 10, "NrEve": 200,
            "NrFrfDataTot": 48, "NrFrfPreData": 0, "NrBlockFrf": 4,
            "NrFrfPre": 6, "NrByteFrfFmy": 48, "NrLamp": 3,
            "cpu_clock_mhz": 300.0,
            "FrfBlocks": [
                {"NrByteFrame": 48, "NrFrfIdxCalMax": 6, "NrIdxPerClass": 6, "NrFrfHold": 2, "NrFrfTot": 8, "LfOptions": 0},
                {"NrByteFrame": 32, "NrFrfIdxCalMax": 4, "NrIdxPerClass": 4, "NrFrfHold": 2, "NrFrfTot": 6, "LfOptions": 0},
                {"NrByteFrame": 24, "NrFrfIdxCalMax": 3, "NrIdxPerClass": 3, "NrFrfHold": 1, "NrFrfTot": 4, "LfOptions": 0},
                {"NrByteFrame": 16, "NrFrfIdxCalMax": 2, "NrIdxPerClass": 2, "NrFrfHold": 1, "NrFrfTot": 3, "LfOptions": 0},
            ],
        },
        "cost_kwargs": {
            "t_main_fixed": 4.9900, "t_gpt_read": 3.9881,
            "t_b1_per_entry": 3.5, "t_async_recurrence": 0.0,
            "t_l1a_per_event_new": 10.0495, "t_l1a_per_event_displace": 11.1695,
            "t_resort_per_entry": 0.0,
            "t_l1b_per_entry_empty": 0.3, "t_l1b_per_entry_valid": 0.0215,
            "t_l1b_resorting": 0.0003, "t_lamp": 1.7359,
            "t_main2_recurrence": 0.0, "t_deferred_base": 18.8587,
            "t_storefrf_no_update": 4.2049, "t_storefrf_free_frame": 0.6516,
            "t_storefrf_full_shift": 1.4618, "t_collect_per_idx": 0.0179,
            "t_collect_fixed": 5.1756, "t_collect_per_entry": 0.4319,
            "t_frfpre_per_entry": 1.0, "t_nvm_onfly": 0.2312,
            "t_frfsrv": 0.0, "t_fct_perm": 2.8069, "t_fct_scdn": 1.3494,
            "t_upd_obd_frf": 1.0894, "k_scenario2_variable": 0.4159,
            "k_proj": 1.0229,
        },
    },
    {
        "project_name": "PROJ5_000U0",
        "source": "Bench measurement Schaeffler ERRM lab, TC387 @ 300 MHz, shared core",
        "fit_rmse": 6.3,
        "calibrations": [(20, 10), (10, 10), (10, 5), (5, 5), (5, 4), (5, 3)],
        "bench": {
            "scenario_1": [1124, 923, 776, 610, 581, 552],
            "scenario_2": [705, 587, 487, 383, 365, 347],
            "scenario_3": [1031, 917, 727, 548, 521, 494],
        },
        "cfg_kwargs": {
            "name": "PROJ5_000U0",
            "NrFmy": 20, "NrFifoBas": 4, "NrFifoIntm": 12, "NrFifoRsv": 4,
            "NrClcFmyEveAsyn": 20, "NrClcFmyPost": 10, "NrEve": 250,
            "NrFrfDataTot": 64, "NrFrfPreData": 0, "NrBlockFrf": 4,
            "NrFrfPre": 8, "NrByteFrfFmy": 64, "NrLamp": 3,
            "cpu_clock_mhz": 300.0,
            "NrClient": 5, "NrCore": 2, "IsSharedCore": True,
            "FrfBlocks": [
                {"NrByteFrame": 48, "NrFrfIdxCalMax": 8, "NrIdxPerClass": 8, "NrFrfHold": 2, "NrFrfTot": 10, "LfOptions": 0},
                {"NrByteFrame": 32, "NrFrfIdxCalMax": 6, "NrIdxPerClass": 6, "NrFrfHold": 2, "NrFrfTot": 8, "LfOptions": 0},
                {"NrByteFrame": 24, "NrFrfIdxCalMax": 4, "NrIdxPerClass": 4, "NrFrfHold": 1, "NrFrfTot": 5, "LfOptions": 0},
                {"NrByteFrame": 16, "NrFrfIdxCalMax": 3, "NrIdxPerClass": 3, "NrFrfHold": 1, "NrFrfTot": 4, "LfOptions": 0},
            ],
        },
        "cost_kwargs": {
            "t_main_fixed": 17.9217, "t_gpt_read": 7.4906,
            "t_b1_per_entry": 2.5, "t_async_recurrence": 0.0,
            "t_l1a_per_event_new": 10.4146, "t_l1a_per_event_displace": 10.5182,
            "t_resort_per_entry": 0.0,
            "t_l1b_per_entry_empty": 0.832, "t_l1b_per_entry_valid": 3.6428,
            "t_l1b_resorting": 0.0026, "t_lamp": 1.0972,
            "t_main2_recurrence": 0.0, "t_deferred_base": 8.4569,
            "t_storefrf_no_update": 1.5410, "t_storefrf_free_frame": 0.6226,
            "t_storefrf_full_shift": 1.8464, "t_collect_per_idx": 0.0016,
            "t_collect_fixed": 0.1116, "t_collect_per_entry": 0.8868,
            "t_frfpre_per_entry": 0.8, "t_nvm_onfly": 0.0151,
            "t_frfsrv": 0.0, "t_fct_perm": 0.0666, "t_fct_scdn": 0.0444,
            "t_upd_obd_frf": 0.0222,
            "t_client_per_client": 12.0, "t_event_db_per_event": 0.18,
            "t_core_sync_per_peer": 9.0, "t_shared_core_penalty": 30.0,
            "t_ptu_profile_penalty": 3.0,
            "k_scenario2_variable": 0.8912, "k_proj": 1.2,
        },
    },
]


SEED_ALIASES: Dict[str, str] = {
    "PROJ1": "PROJ1_0U0_OB6_023",
    "PROJ3": "PROJ3_0U0_P16_624",
}