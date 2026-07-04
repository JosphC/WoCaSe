"""
Main Application Module

Orchestrates the entire WCS test configuration workflow.
"""

import os
from typing import Optional, List, Tuple
from pathlib import Path

from .logging_config import get_logger
from . import (
    arxml_processor,
    code_modifier,
    file_generator,
    gpt_detector,
    path_utils,
    td5_builder,
    tdcl_modifier,
    xml_modifier,
    simulator_bridge,
)

logger = get_logger(__name__)

# Constants
_TARGET_FOLDER = r"errm_fctdg_test\i"


class InstrumentationError(RuntimeError):
    """Raised when one or more instrumentation operations cannot be completed.

    Attributes:
        failures: list of (operation_name, detail) tuples describing each
                  problem detected during the validation phase.
    """

    def __init__(self, failures: List[Tuple[str, str]]):
        self.failures = failures
        lines = ["Instrumentation cannot be performed. Detected issues:\n"]
        for op, detail in failures:
            lines.append(f"• [{op}] {detail}")
        super().__init__("\n".join(lines))


def _validate_instrumentation(case_name: str, work_dir: str):
    """Validate **all** preconditions before any file is touched.

    Returns a dict with every piece of data the apply phase needs,
    or raises *InstrumentationError* listing every problem found.
    """
    failures: List[Tuple[str, str]] = []
    ctx: dict = {}                       # collected context for apply phase

    # 1. GPT function pair --------------------------------------------------
    func_pair = gpt_detector.find_function_pair_in_headers(work_dir)
    if func_pair is None:
        failures.append((
            "GPT Functions",
            "The GPT functions (convert / gettime) were not found in the headers in work_dir."
        ))
    else:
        ctx['convert_func'], ctx['gettime_func'] = func_pair

    # 2. Required source files -----------------------------------------------
    arxml_abs_path = path_utils.find_project_file(
        "icsp_dem_genr_cnf_spec.arxml", case_name)
    if arxml_abs_path is None:
        failures.append((
            "ARXML File",
            "The file 'icsp_dem_genr_cnf_spec.arxml' was not found in the project."
        ))
    ctx['arxml_abs_path'] = arxml_abs_path

    main_abs_path = path_utils.find_project_file("icsp_dem_main.c", case_name)
    if main_abs_path is None:
        failures.append((
            "main.c File",
            "The file 'icsp_dem_main.c' was not found in the project."
        ))
    ctx['main_abs_path'] = main_abs_path

    # 3. ARXML processing (read-only) ----------------------------------------
    if arxml_abs_path is not None:
        result = arxml_processor.process_arxml(arxml_abs_path)
        if result is None or result[0] is None:
            failures.append((
                "ARXML Processing",
                f"ARXML file processing failed: {arxml_abs_path}"
            ))
        else:
            ctx['val'], ctx['val_x_2'] = result

    # 4. Target folder for generated files -----------------------------------
    folder_found = path_utils.find_folder(work_dir, _TARGET_FOLDER)
    if folder_found is None:
        failures.append((
            "Target Folder",
            f"The folder '{_TARGET_FOLDER}' was not found in the project."
        ))
    ctx['folder_found'] = folder_found

    # 5. TDCL file existence check -------------------------------------------
    from .tdcl_modifier import _TARGET_FILENAMES as _TDCL_NAMES  # noqa: WPS433
    tdcl_found = False
    for root, _dirs, files in os.walk(work_dir, topdown=True):
        for fn in files:
            if fn in _TDCL_NAMES:
                tdcl_found = True
                break
        if tdcl_found:
            break
    if not tdcl_found:
        failures.append((
            "TDCL File",
            "No TDCL file (project_options.tdcl / errm.tdcl / errm_agf.tdcl) was found."
        ))

    # 6. CBD file for xml_modifier -------------------------------------------
    cbd_file = xml_modifier.find_cbd_file(case_name)
    if cbd_file is None:
        failures.append((
            "CBD File",
            "No .cbd file (icsp_dem_cnf.cbd / icsp_dem_cnf_sw.cbd) was found."
        ))
    ctx['cbd_file'] = cbd_file

    # ── verdict ─────────────────────────────────────────────────────────────
    if failures:
        raise InstrumentationError(failures)

    return ctx


def _execute_instrumentation(case_name: str, work_dir: str, ctx: dict) -> None:
    """Execute all instrumentation operations (called only after validation)."""

    folder_found = ctx['folder_found']
    val = ctx['val']
    val_x_2 = ctx['val_x_2']
    convert_func = ctx['convert_func']
    gettime_func = ctx['gettime_func']
    main_abs_path = ctx['main_abs_path']
    cbd_file = ctx['cbd_file']

    # 1. Create generated files
    logger.info("Folder found: %s", folder_found)
    file_generator.create_cbd_file_at(folder_found)
    file_generator.create_errm_wcs_dcnfxml(folder_found, val_x_2 - 1)
    file_generator.create_errm_wcs_grl(folder_found, val_x_2)

    # 2. TDCL include
    result = tdcl_modifier.find_and_insert_errm_include(work_dir)
    if result:
        logger.info("File modified/found: %s", result)

    # 3. main.c modifications (headers + execution-time block)
    code_modifier.add_headers_to_main_c(main_abs_path)
    code_modifier.modify_main_c(main_abs_path, val, convert_func, gettime_func)

    # 4. CBD / XML modifications
    xml_modifier.modify_icsp_dem_cbd(cbd_file)
    xml_modifier.path_insert_xml(case_name)

    logger.info("All instrumentation operations completed successfully.")


def apply_modifications(case_name: str, work_dir: str) -> None:
    """
    Applies all necessary modifications to the project files.

    Uses a two-phase (validate → execute) approach so that **no file is
    modified** unless every single operation can be performed.  If any
    precondition is not met an *InstrumentationError* is raised with
    details about every problem found.

    Args:
        case_name: Path to the case directory
        work_dir: Path to the work directory

    Raises:
        InstrumentationError: when one or more operations cannot proceed.
    """
    ctx = _validate_instrumentation(case_name, work_dir)   # may raise
    _execute_instrumentation(case_name, work_dir, ctx)


def process_system_file(
    proj_name: str,
    td5_path: str,
    build_type: str,
    rule: str,
    *,
    target_name: Optional[str] = None,
    run_simulation: bool = False,
    sim_generate_excel: bool = True,
    sim_run_monte_carlo: bool = True,
    sim_mc_cycles: int = 50_000,
    sim_yellow_threshold: int = 500,
    progress_callback=None,
) -> Optional['simulator_bridge.SimulationResults']:
    """
    Processes a System File project.
    
    Args:
        proj_name: Project name
        td5_path: Path to TD5 executable
        build_type: Build type (e.g., "NORMAL")
        rule: Build rule (e.g., "All")
        target_name: Optional target name (auto-detected if not given)
        run_simulation: Whether to run DEM simulation after build
        sim_generate_excel: Generate Excel report from simulation
        sim_run_monte_carlo: Run Monte Carlo analysis
        sim_mc_cycles: Number of Monte Carlo cycles
        sim_yellow_threshold: Yellow highlight threshold in µs for Excel report
        progress_callback: Callback for progress updates

    Returns:
        SimulationResults if run_simulation is True, else None
    """
    logger.info("=== Processing System File project: %s ===", proj_name)
    
    case_name = path_utils.create_case_path(proj_name)
    if not case_name:
        raise RuntimeError("Failed to create valid project path!")
    

    case_path = Path(case_name).resolve()
    if not case_path.exists():
        raise RuntimeError(f"Project path does not exist: {case_path}")
    
    work_dir = path_utils.find_first_work_subdir(case_name)
    if not work_dir:
        raise RuntimeError("Work directory not found!")
    

    apply_modifications(case_name, work_dir)

    if not target_name:
        target_name = td5_builder.find_target_name_recursively(work_dir)
    if not target_name:
        raise RuntimeError("Target name not found!")
    
    td5_builder.importfs(td5_path, case_name, proj_name)
    td5_builder.buildprj(td5_path, proj_name, target_name, build_type, rule)

    # --- Post-build: DEM Simulation ---
    if run_simulation:
        logger.info("=== Starting post-build DEM simulation ===")
        return simulator_bridge.run_post_build_simulation(
            case_path=case_name,
            proj_name=proj_name,
            generate_excel=sim_generate_excel,
            run_monte_carlo=sim_run_monte_carlo,
            mc_cycles=sim_mc_cycles,
            yellow_threshold=sim_yellow_threshold,
            progress_callback=progress_callback,
        )
    return None

def process_mks_release(
    release_name: str,
    td5_path: str,
    build_type: str,
    rule: str,
    *,
    target_name: Optional[str] = None,
    run_simulation: bool = False,
    sim_generate_excel: bool = True,
    sim_run_monte_carlo: bool = True,
    sim_mc_cycles: int = 50_000,
    sim_yellow_threshold: int = 500,
    progress_callback=None,
) -> Optional['simulator_bridge.SimulationResults']:
    """
    Processes an MKS release.
    
    Args:
        release_name: Release name
        td5_path: Path to TD5 executable
        build_type: Build type (e.g., "NORMAL")
        rule: Build rule (e.g., "All")
        target_name: Optional target name (auto-detected if not given)
        run_simulation: Whether to run DEM simulation after build
        sim_generate_excel: Generate Excel report from simulation
        sim_run_monte_carlo: Run Monte Carlo analysis
        sim_mc_cycles: Number of Monte Carlo cycles
        sim_yellow_threshold: Yellow highlight threshold in µs for Excel report
        progress_callback: Callback for progress updates

    Returns:
        SimulationResults if run_simulation is True, else None
    """
    logger.info("=== Processing MKS release: %s ===", release_name)
    
    case_name = path_utils.create_case_path(release_name)
    if not case_name:
        raise RuntimeError("Failed to create valid project path!")

    td5_builder.importmks(td5_path, release_name)
    
    if not os.path.exists(case_name):
        raise RuntimeError(f"Project path does not exist: {case_name}")
    
    work_dir = path_utils.find_first_work_subdir(case_name)
    if not work_dir:
        raise RuntimeError("Work directory not found!")

    apply_modifications(case_name, work_dir)
    if not target_name:
        target_name = td5_builder.find_target_name_recursively(work_dir)
    
    if not target_name:
        raise RuntimeError("Target name not found!")
    
    base_folder = os.path.basename(case_name)
    td5_builder.importfs(td5_path, case_name, base_folder)
    td5_builder.buildprj(td5_path, base_folder, target_name, build_type, rule)

    # --- Post-build: DEM Simulation ---
    if run_simulation:
        logger.info("=== Starting post-build DEM simulation ===")
        return simulator_bridge.run_post_build_simulation(
            case_path=case_name,
            proj_name=release_name,
            generate_excel=sim_generate_excel,
            run_monte_carlo=sim_run_monte_carlo,
            mc_cycles=sim_mc_cycles,
            yellow_threshold=sim_yellow_threshold,
            progress_callback=progress_callback,
        )
    return None
