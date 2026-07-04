"""
=============================================================================
  DEM MainFunction Runtime Simulator  (Multi-Project, Excel Output)
  -----------------------------------------------------------------
  Version : 2.0.0
  Predicts debug_dem_highest_time for Icsp_Dem_MainFunction()

  Source reference : work/bsw/icsp/dem/dem/pi/main/i/icsp_dem_main.c

  Supported projects (anonymized project codes; PROJ2/PROJ3 stand in for
  real company ECU projects):
    PROJ2_0U0_OB6_024   (Aurix TC3xx, STM @ 50 MHz, CPU @ 300 MHz)
    PROJ3_0U0_P16_624   (Aurix TC3xx, STM @ 50 MHz, CPU @ 300 MHz)

  Build flavours (per project):
    _FS_PROJxx_0U0_NORMAL   (debug  -- metric exists here)
    _FS_PROJxx_0U0_RELEASE  (production -- metric stripped)
=============================================================================
"""

from __future__ import annotations

__version__ = "2.1.0"

# Re-export public API for convenience
from dem_simulator.exceptions import (
    SimulatorError,
    ConfigValidationError,
    FitConvergenceError,
    ExcelReportError,
)
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
    SENSITIVITY_POST_VALS,
    SENSITIVITY_EA_VALS,
    ScenarioType,
)


from dem_simulator.config import (
    FrfBlockConfig,
    ProjectConfig,
    ProjectDefinition,
)
from dem_simulator.costs import (
    MicroCosts,
    COSTS_PROJ1,
    COSTS_PROJ2,
    COSTS_PROJ3,
    PROJECT_COSTS,
)
from dem_simulator.scenarios import (
    Scenario,
    SCENARIOS,
    WCS_SCENARIO_KEYS,
    CALIBRATIONS,
    build_scenarios,
)
from dem_simulator.config import DEFAULT_CALIBRATIONS
from dem_simulator.engine import DemMainFunctionSimulator
from dem_simulator.simulation import (
    simulate_wcs_grid,
    simulate_with_breakdown,
    compute_rmse,
    compute_per_scenario_rmse,
    FitResult,
    auto_fit,
)
from dem_simulator.analysis import (
    MonteCarloResult,
    simulate_peak_runtime,
    build_deterministic_scenarios,
    sensitivity_analysis,
    cross_variant_comparison,
    load_config_from_json,
    apply_json_config,
)
from dem_simulator.selftest import run_self_tests
from dem_simulator.excel_report import generate_excel_report
from dem_simulator.logging_setup import setup_logging, logger
from dem_simulator.extractor import (
    load_project_from_c,
    extract_project_config,
    extract_ptu_variants,
)
