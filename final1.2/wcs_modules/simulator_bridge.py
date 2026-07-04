"""
Simulator Bridge Module

Bridges the WCS instrumental tool with the DEM MainFunction Runtime Simulator.
After a TD5 build completes, this module:
  1. Locates the generated icsp_dem_cnf.c in the built project
  2. Locates PTU header files for variant calibration overrides
  3. Extracts all calibration values using dem_simulator.extractor
  4. Runs the WCS grid simulation (3 scenarios x 6 calibrations)
  5. Optionally generates an Excel report

This enables the full workflow:
  Instrument → Build → Extract → Simulate → Report
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class SimulationResults:
    """Container for DEM simulation results returned to the UI."""

    project_name: str = ""
    # Extracted configuration summary
    nr_fmy: int = 0
    nr_eve: int = 0
    nr_frf_data_tot: int = 0
    nr_block_frf: int = 0
    nr_frf_pre: int = 0
    nr_lamp: int = 0
    nr_clc_fmy_eve_asyn: int = 0
    nr_clc_fmy_post: int = 0
    # WCS grid results  { "S1": [727, 601, ...], "S2": [...], "S3": [...] }
    wcs_grid: Dict[str, List[float]] = field(default_factory=dict)
    # Per-scenario RMSE (if bench reference available)
    rmse_total: float = 0.0
    rmse_per_scenario: Dict[str, float] = field(default_factory=dict)
    # Monte Carlo summary
    mc_peak_us: float = 0.0
    mc_mean_us: float = 0.0
    mc_p99_us: float = 0.0
    # Path to generated Excel report (empty if not generated)
    excel_path: str = ""
    # Whether bench reference data was available
    has_reference: bool = False
    # Any warnings collected during the process
    warnings: List[str] = field(default_factory=list)
    # Number of PTU variants found
    num_variants: int = 0
    # Calibration labels for the grid columns
    calibration_labels: List[str] = field(default_factory=list)
    # Success flag
    success: bool = False
    error_message: str = ""


# ---------------------------------------------------------------------------
# Path discovery helpers
# ---------------------------------------------------------------------------

def _find_cnf_c_file(case_path: str) -> Optional[str]:
    """Locate ``icsp_dem_cnf.c`` within the project tree.

    Searches under the ``work`` directory first (most common location),
    then falls back to a full recursive scan of the case path.
    """
    target_name = "icsp_dem_cnf.c"
    # Try the standard output location first
    for dirpath, _, filenames in os.walk(case_path):
        for fn in filenames:
            if fn.lower() == target_name:
                full = os.path.join(dirpath, fn)
                logger.info("Found %s at: %s", target_name, full)
                return full
    return None


def _find_ptu_dir(case_path: str) -> Optional[str]:
    """Locate the PTU header directory within the project tree.

    Standard path: ``work/bsw/icsp/dem/dem/pi/main/t``
    Falls back to searching for any directory containing ``icsp_dem_cnf_ptu*.h``.
    """
    import glob

    # Try standard relative path
    for dirpath, dirnames, _ in os.walk(case_path):
        rel = os.path.relpath(dirpath, case_path)
        parts = Path(rel).parts
        if len(parts) >= 3 and parts[-3:] == ("main", "t",):
            # Check for PTU files
            ptu_files = glob.glob(os.path.join(dirpath, "icsp_dem_cnf_ptu*.h"))
            if ptu_files:
                logger.info("Found PTU directory: %s (%d files)", dirpath, len(ptu_files))
                return dirpath

    # Broad search: any folder with ptu headers
    for dirpath, _, filenames in os.walk(case_path):
        ptu_matches = [f for f in filenames if f.lower().startswith("icsp_dem_cnf_ptu") and f.lower().endswith(".h")]
        if ptu_matches:
            logger.info("Found PTU directory (fallback): %s (%d files)", dirpath, len(ptu_matches))
            return dirpath

    logger.warning("No PTU header directory found under %s", case_path)
    return None


def _infer_project_key(proj_name: str) -> str:
    """Infer the short project key (e.g. 'PROJ3') from the full project name.

    Examples:
        'PROJ3_0U0_P16_624' -> 'PROJ3'
        'PROJ2_0U0_OB6_024' -> 'PROJ2'
        'PROJ3'             -> 'PROJ3'
    """
    return proj_name.split("_")[0].upper()


# ---------------------------------------------------------------------------
# Main bridge function
# ---------------------------------------------------------------------------

def run_post_build_simulation(
    case_path: str,
    proj_name: str,
    *,
    generate_excel: bool = True,
    run_monte_carlo: bool = True,
    mc_cycles: int = 50_000,
    yellow_threshold: int = 500,
    output_dir: Optional[str] = None,
    progress_callback=None,
) -> SimulationResults:
    """Run the DEM simulator on a freshly built project.

    This is the main integration point called after ``td5_builder.buildprj``
    completes.  It extracts calibration values from the generated C sources,
    runs the WCS grid simulation, and optionally generates an Excel report.

    Parameters
    ----------
    case_path : str
        Root path of the instrumented project
        (e.g. ``d:\\casdev\\td5\\PR\\OJ3\\P16\\PROJ3_0U0_P16_624``).
    proj_name : str
        Project/release name as entered by the user.
    generate_excel : bool
        Whether to generate an Excel report.
    run_monte_carlo : bool
        Whether to run Monte Carlo analysis (can be slow).
    mc_cycles : int
        Number of Monte Carlo cycles if enabled.
    output_dir : str, optional
        Directory for the Excel report.  Defaults to ``case_path``.
    progress_callback : callable, optional
        ``callback(message: str)`` for progress updates.

    Returns
    -------
    SimulationResults
        Full results including extracted config, WCS grid, and report path.
    """
    result = SimulationResults(project_name=proj_name)

    def _progress(msg: str):
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    # ------------------------------------------------------------------
    # Step 1: Import the simulator (may fail if not installed)
    # ------------------------------------------------------------------
    try:
        from dem_simulator.extractor import (
            load_project_from_c,
            get_project_reference,
        )
        from dem_simulator.costs import get_project_costs
        from dem_simulator.simulation import simulate_wcs_grid, compute_rmse, compute_per_scenario_rmse
        from dem_simulator.analysis import simulate_peak_runtime
        from dem_simulator.excel_report import generate_excel_report
        from dem_simulator.scenarios import CALIBRATIONS
        from dem_simulator import __version__ as sim_version
    except ImportError as e:
        result.error_message = f"DEM Simulator not available: {e}"
        logger.error(result.error_message)
        return result

    # ------------------------------------------------------------------
    # Step 2: Locate generated C sources
    # ------------------------------------------------------------------
    _progress("[SIM] Step 1/5: Locating generated C source files...")

    cnf_c_path = _find_cnf_c_file(case_path)
    if not cnf_c_path:
        result.error_message = (
            f"Could not find icsp_dem_cnf.c under {case_path}. "
            "The build may not have generated the expected output files."
        )
        logger.error(result.error_message)
        return result

    ptu_dir = _find_ptu_dir(case_path)

    # ------------------------------------------------------------------
    # Step 3: Extract calibration values
    # ------------------------------------------------------------------
    _progress("[SIM] Step 2/5: Extracting calibration values from C sources...")

    project_key = _infer_project_key(proj_name)
    reference_wcs = get_project_reference(proj_name) or {}
    result.has_reference = bool(reference_wcs)

    try:
        project_def = load_project_from_c(
            cnf_c_path=cnf_c_path,
            project_name=project_key,
            ptu_dir=ptu_dir,
            description=f"{proj_name} (extracted after build)",
            reference_wcs=reference_wcs,
        )
    except Exception as e:
        result.error_message = f"Failed to extract configuration: {e}"
        logger.error(result.error_message)
        return result

    cfg = project_def.default_config
    result.nr_fmy = cfg.NrFmy
    result.nr_eve = cfg.NrEve
    result.nr_frf_data_tot = cfg.NrFrfDataTot
    result.nr_block_frf = cfg.NrBlockFrf
    result.nr_frf_pre = cfg.NrFrfPre
    result.nr_lamp = cfg.NrLamp
    result.nr_clc_fmy_eve_asyn = cfg.NrClcFmyEveAsyn
    result.nr_clc_fmy_post = cfg.NrClcFmyPost
    result.num_variants = len(project_def.variant_configs)

    _progress(
        f"[SIM]   Extracted: NrFmy={cfg.NrFmy}, NrEve={cfg.NrEve}, "
        f"NrFrfDataTot={cfg.NrFrfDataTot}, NrBlockFrf={cfg.NrBlockFrf}, "
        f"NrLamp={cfg.NrLamp}, NrFrfPre={cfg.NrFrfPre}"
    )
    _progress(
        f"[SIM]   Calibration: EveAsyn={cfg.NrClcFmyEveAsyn}, "
        f"Post={cfg.NrClcFmyPost}, Variants={result.num_variants}"
    )

    # ------------------------------------------------------------------
    # Step 4: Select or create cost model
    # ------------------------------------------------------------------
    _progress("[SIM] Step 3/5: Running WCS grid simulation...")

    costs = get_project_costs(proj_name, cfg=cfg)

    # Build calibration labels
    result.calibration_labels = [f"({a},{p})" for a, p in CALIBRATIONS]

    # Run WCS grid
    try:
        result.wcs_grid = simulate_wcs_grid(cfg, costs)
    except Exception as e:
        result.error_message = f"WCS grid simulation failed: {e}"
        logger.error(result.error_message)
        return result

    # Log results
    for skey, row in result.wcs_grid.items():
        _progress(f"[SIM]   {skey}: {row} µs")

    # ------------------------------------------------------------------
    # Step 5: RMSE comparison (if bench data available)
    # ------------------------------------------------------------------
    if result.has_reference:
        _progress("[SIM] Step 4/5: Computing RMSE against bench reference...")
        try:
            result.rmse_total = compute_rmse(cfg, costs, reference_wcs)
            result.rmse_per_scenario = compute_per_scenario_rmse(cfg, costs, reference_wcs)
            _progress(f"[SIM]   Total RMSE: {result.rmse_total:.2f} µs")
            for sk, rv in result.rmse_per_scenario.items():
                _progress(f"[SIM]   {sk} RMSE: {rv:.2f} µs")
        except Exception as e:
            result.warnings.append(f"RMSE computation failed: {e}")
            logger.warning("RMSE computation failed: %s", e)
    else:
        _progress("[SIM] Step 4/5: No bench reference data - RMSE skipped.")

    # ------------------------------------------------------------------
    # Step 6: Monte Carlo (optional)
    # ------------------------------------------------------------------
    if run_monte_carlo:
        _progress(f"[SIM] Step 5/5: Running Monte Carlo simulation ({mc_cycles:,} cycles)...")
        try:
            mc = simulate_peak_runtime(cfg, costs, num_cycles=mc_cycles)
            result.mc_peak_us = mc.peak_us
            result.mc_mean_us = mc.mean_us
            result.mc_p99_us = mc.p99_us
            _progress(
                f"[SIM]   MC Results: Peak={mc.peak_us:.1f} µs, "
                f"Mean={mc.mean_us:.1f} µs, P99={mc.p99_us:.1f} µs "
                f"({mc.elapsed_sec:.1f}s)"
            )
        except Exception as e:
            result.warnings.append(f"Monte Carlo failed: {e}")
            logger.warning("Monte Carlo failed: %s", e)
    else:
        _progress("[SIM] Step 5/5: Monte Carlo skipped.")

    # ------------------------------------------------------------------
    # Step 7: Excel report (optional)
    # ------------------------------------------------------------------
    if generate_excel:
        _progress("[SIM] Generating Excel report...")
        report_dir = output_dir or case_path
        report_name = f"results_wcs_{project_key}.xlsx"
        report_path = os.path.join(report_dir, report_name)
        try:
            saved_path = generate_excel_report(
                cfg=cfg,
                costs=costs,
                output_path=report_path,
                project=project_def,
                include_monte_carlo=run_monte_carlo,
                mc_cycles=mc_cycles,
                version=sim_version,
                yellow_threshold=yellow_threshold,
            )
            result.excel_path = saved_path
            _progress(f"[SIM]   Excel report saved: {saved_path}")
        except Exception as e:
            result.warnings.append(f"Excel report failed: {e}")
            logger.warning("Excel report generation failed: %s", e)

    result.success = True
    _progress("[SIM]   Simulation completed successfully.")
    return result
