"""CLI entry-point for the DEM MainFunction Runtime Simulator.

Run with:
    python -m dem_simulator              # interactive project select
    python -m dem_simulator PROJ2        # run PROJ2 only
    python -m dem_simulator PROJ3        # run PROJ3 only
    python -m dem_simulator ALL          # run all projects
    python -m dem_simulator --fit        # auto-fit costs then run
    python -m dem_simulator --selftest   # run built-in validation
"""


from __future__ import annotations

import argparse
import os
import sys
import textwrap
from typing import Any, Dict, List, Optional, Tuple

from dem_simulator import __version__
from dem_simulator.logging_setup import setup_logging, logger
from dem_simulator.exceptions import SimulatorError
from dem_simulator.constants import MC_DEFAULT_CYCLES, MC_DEFAULT_SEED
from dem_simulator.config import ProjectDefinition
from dem_simulator.extractor import load_project_from_c, discover_projects
from dem_simulator.costs import (
    MicroCosts,
    COSTS_PROJ1,
    COSTS_PROJ2,
    COSTS_PROJ3,
    PROJECT_COSTS,
    get_project_costs,
)
from dem_simulator.scenarios import SCENARIOS, WCS_SCENARIO_KEYS, CALIBRATIONS, build_scenarios
from dem_simulator.config import DEFAULT_CALIBRATIONS
from dem_simulator.simulation import (
    simulate_wcs_grid,
    compute_rmse,
    auto_fit,
    simulate_with_breakdown,
)
from dem_simulator.analysis import (
    cross_variant_comparison,
    load_config_from_json,
    apply_json_config,
)
from dem_simulator.extractor import load_project_from_c
from dem_simulator.selftest import run_self_tests
from dem_simulator.excel_report import generate_excel_report

# ==============================================================================
# PROJECTS — loaded dynamically at import time from the standard directory layout
# ==============================================================================

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS: Dict[str, ProjectDefinition] = discover_projects(_BASE_DIR)
if not PROJECTS:
    logger.debug(
        "No projects found in %s — use --from-project for manual loading.",
        _BASE_DIR,
    )


# ==============================================================================
# CLI argument parser
# ==============================================================================

def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "DEM MainFunction Runtime Simulator — multi-project, "
            "Excel output."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s PROJ3               Run PROJ3 only
              %(prog)s ALL --fit           Fit all projects
              %(prog)s PROJ2 --dry-run     Preview without saving
              %(prog)s --selftest          Run built-in validation
              %(prog)s --config costs.json Override micro-costs from JSON
        """),
    )
    parser.add_argument(
        "project", nargs="?", default=None,
        help="Project key (e.g. PROJ2, PROJ3) or ALL.  "
             "Omit for interactive selection.",
    )
    parser.add_argument(
        "--fit", action="store_true",
        help="Auto-fit micro-costs to bench reference data.",
    )
    parser.add_argument(
        "--selftest", action="store_true",
        help="Run built-in self-tests and exit.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable DEBUG-level logging.",
    )
    parser.add_argument(
        "--output-dir", "-o", default=None,
        help="Directory for output files (default: script directory).",
    )
    parser.add_argument(
        "--config", default=None,
        help="Path to a JSON config file for micro-cost overrides.",
    )
    parser.add_argument(
        "--log-file", default=None,
        help="Write log output to a file in addition to console.",
    )
    parser.add_argument(
        "--no-monte-carlo", action="store_true",
        help="Skip Monte Carlo sheet in Excel output.",
    )
    parser.add_argument(
        "--mc-cycles", type=int, default=MC_DEFAULT_CYCLES,
        help=f"Number of Monte Carlo cycles (default: {MC_DEFAULT_CYCLES:,}).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print simulation results without generating Excel files.",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--from-project", default=None,
        metavar="CNF_C_PATH",
        help=(
            "Extract the configuration dynamically from the generated C file "
            "(icsp_dem_cnf.c). Example: "
            "--from-project PROJ3/_FS_PROJ3_0U0_NORMAL/proc/ARPROC/out/icsp_dem_cnf.c"
        ),
    )
    parser.add_argument(
        "--ptu-dir", default=None,
        metavar="DIR",
        help=(
            "Directory containing icsp_dem_cnf_ptu*.h files for PTU variants. "
            "Used together with --from-project."
        ),
    )
    return parser


# ==============================================================================
# Project selection
# ==============================================================================

def _select_project(
    requested: Optional[str] = None,
) -> Tuple[str, Optional[ProjectDefinition]]:
    """Resolve the project key.  Falls back to interactive menu."""
    if requested and requested.upper() in PROJECTS:
        key = requested.upper()
        return key, PROJECTS[key]

    if requested and requested.upper() == "ALL":
        return "ALL", None

    # Interactive selection
    logger.info("")
    logger.info("  Available projects:")
    for i, (k, p) in enumerate(sorted(PROJECTS.items()), 1):
        logger.info("    %d. %s  --  %s", i, k, p.description)
    logger.info("    %d. ALL  --  Run all projects", len(PROJECTS) + 1)

    try:
        choice = input("\n  Select project [1]: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    if not choice or choice == "1":
        key = sorted(PROJECTS.keys())[0]
    elif choice == str(len(PROJECTS) + 1) or choice.upper() == "ALL":
        return "ALL", None
    else:
        try:
            idx = int(choice) - 1
            key = sorted(PROJECTS.keys())[idx]
        except (ValueError, IndexError):
            key = sorted(PROJECTS.keys())[0]
    return key, PROJECTS[key]


# ==============================================================================
# Single-project runner
# ==============================================================================

def _run_project(
    project: ProjectDefinition,
    *,
    output_dir: Optional[str] = None,
    dry_run: bool = False,
    include_monte_carlo: bool = True,
    mc_cycles: int = MC_DEFAULT_CYCLES,
    mc_seed: int = MC_DEFAULT_SEED,
    config_overrides: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Run the full simulation pipeline for a single project.

    Parameters
    ----------
    project : ProjectDefinition
        The project to simulate.
    output_dir : str, optional
        Directory for output files.
    dry_run : bool
        If True, print results but do not generate Excel.
    include_monte_carlo : bool
        Whether to include the Monte Carlo sheet.
    mc_cycles : int
        Number of Monte Carlo cycles.
    mc_seed : int
        RNG seed for Monte Carlo.
    config_overrides : dict, optional
        JSON config overrides to apply to micro-costs.

    Returns
    -------
    str or None
        Absolute path of the saved Excel file, or None for dry runs.
    """
    cfg = project.default_config
    proj_name = project.name
    costs = get_project_costs(proj_name, cfg)
    ref_wcs = project.reference_wcs
    has_reference = bool(ref_wcs)

    # Apply JSON config overrides if any
    if config_overrides:
        new_cfg, new_costs = apply_json_config(
            config_overrides, proj_name, base_cfg=cfg,
        )
        if new_cfg:
            cfg = new_cfg
        if new_costs:
            costs = new_costs

    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, f"results_wcs_{proj_name}.xlsx")


    # ── Console WCS grid ──────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 78)
    logger.info("  WCS SIMULATION RESULTS  (%s)", proj_name)
    logger.info("=" * 78)
    logger.info(
        "  Config: NrFmy=%d  NrEve=%d  NrLamp=%d  NrFrfDataTot=%d",
        cfg.NrFmy, cfg.NrEve, cfg.NrLamp, cfg.NrFrfDataTot,
    )

    grid = simulate_wcs_grid(cfg, costs, project.calibrations)

    cal_hdr = f"  {'Scenario':<35s}"
    for i, (a, p) in enumerate(project.calibrations, 1):
        cal_hdr += f"  Cal{i}({a}/{p})"
    logger.info(cal_hdr)
    logger.info("  " + "-" * 90)

    scenarios = build_scenarios(
        nr_inject_first=cfg.nr_inject_first,
        nr_inject_next=cfg.nr_inject_next,
        nr_fmy=cfg.NrFmy,
    )
    for si, scenario in enumerate(scenarios):
        skey = WCS_SCENARIO_KEYS[si]
        row_str = f"  {scenario.name:<35s}"
        for v in grid[skey]:
            row_str += f"  {v:>10.0f}"
        logger.info(row_str)

    # ── RMSE ──────────────────────────────────────────────────────────────────
    if has_reference:
        rmse = compute_rmse(cfg, costs, ref_wcs, project.calibrations)
        logger.info("")
        logger.info("  Overall RMSE = %.1f \u00b5s", rmse)

    # ── Reference comparison ──────────────────────────────────────────────────
    if has_reference:
        logger.info("")
        logger.info("=" * 78)
        logger.info("  COMPARISON WITH BENCH REFERENCE  (%s)", proj_name)
        logger.info("=" * 78)
        for si, scenario in enumerate(scenarios):
            skey = WCS_SCENARIO_KEYS[si]
            logger.info("")
            logger.info("  %s", scenario.name)
            logger.info("  %10s  %8s  %8s  %8s", "Cal", "Ref", "Sim", "Diff")
            logger.info("  %s", "=" * 40)
            ref_values = ref_wcs.get(skey, [])
            for ci, (a, p) in enumerate(project.calibrations):
                ref = ref_values[ci] if ci < len(ref_values) else 0
                sim_v = grid[skey][ci]
                diff = ((sim_v - ref) / ref) * 100 if ref else 0.0
                logger.info(
                    "  %s/%2d       %8d  %8.0f  %+7.1f%%", a, p, ref, sim_v, diff,
                )

        # Detailed breakdown for Cal_1
        cal1_asyn, cal1_post = project.calibrations[0]
        logger.info("")
        logger.info("  Detailed breakdown for %s, Cal_1 (%d/%d):", proj_name, cal1_asyn, cal1_post)
        logger.info("  %-25s %8s %8s %8s", "Phase", "Scen1", "Scen2", "Scen3")
        logger.info("  %s", "-" * 55)
        all_phase_data: Dict[str, List[float]] = {}
        all_phase_share: Dict[str, List[float]] = {}
        for _si, scenario in enumerate(scenarios):
            breakdown = simulate_with_breakdown(
                cfg, costs, scenario, cal1_asyn, cal1_post,
            )
            bd = breakdown["phase_us"]
            shares = breakdown["phase_share_pct"]
            for ph, v in bd.items():
                all_phase_data.setdefault(ph, []).append(v)
                all_phase_share.setdefault(ph, []).append(shares.get(ph, 0.0))
        for ph, vals in all_phase_data.items():
            logger.info(
                "  %-25s %8.1f %8.1f %8.1f", ph, vals[0], vals[1], vals[2],
            )
            shr = all_phase_share.get(ph, [0.0, 0.0, 0.0])
            logger.info(
                "  %-25s %7.1f%% %7.1f%% %7.1f%%",
                "  share", shr[0], shr[1], shr[2],
            )
        totals = [
            sum(all_phase_data[ph][i] for ph in all_phase_data) for i in range(3)
        ]
        logger.info(
            "  %-25s %8.1f %8.1f %8.1f", "TOTAL", totals[0], totals[1], totals[2],
        )
    else:
        logger.info("")
        logger.info("  (i) No bench reference data available for %s.", proj_name)
        logger.info(
            "      Simulated values are predictions based on fitted timing constants.",
        )

    # ── Cross-variant comparison ──────────────────────────────────────────────
    cross_variant_comparison(costs, project=project)

    # ── Generate Excel report ─────────────────────────────────────────────────
    if dry_run:
        logger.info("")
        logger.info("  [dry-run] Skipping Excel report generation.")
        return None

    saved = generate_excel_report(
        cfg, costs, output_path, project=project,
        include_monte_carlo=include_monte_carlo,
        mc_cycles=mc_cycles, mc_seed=mc_seed,
    )
    logger.info("  All %s results written to: %s", proj_name, saved)
    return saved


# ==============================================================================
# Main CLI entry-point
# ==============================================================================

def main() -> int:
    """CLI entry-point.  Returns exit code (0 = success)."""
    parser = _build_arg_parser()
    args = parser.parse_args()

    # ── Logging setup ─────────────────────────────────────────────────────────
    setup_logging(verbose=args.verbose, log_file=args.log_file)

    logger.info("=" * 68)
    logger.info(
        "  DEM MainFunction Runtime Simulator  v%s", __version__,
    )
    logger.info("=" * 68)

    # ── Self-test mode ────────────────────────────────────────────────────────
    if args.selftest:
        ok = run_self_tests()
        return 0 if ok else 1

    # ── Load JSON config if provided ──────────────────────────────────────────
    config_overrides: Optional[Dict[str, Any]] = None
    if args.config:
        config_overrides = load_config_from_json(args.config)
        logger.info("Loaded config overrides from: %s", args.config)

    # ── Output directory ──────────────────────────────────────────────────────
    output_dir = args.output_dir
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        logger.info("Created output directory: %s", output_dir)

    # ── Dynamic loading from the C file (--from-project) ─────────────────────
    if args.from_project:
        proj_name = (args.project or "PROJECT").upper()
        logger.info("Extracting configuration from: %s", args.from_project)
        try:
            from dem_simulator.extractor import get_project_reference
            dyn_project = load_project_from_c(
                cnf_c_path   = args.from_project,
                project_name = proj_name,
                ptu_dir      = args.ptu_dir,
                reference_wcs= get_project_reference(proj_name),
                nr_client    = 6,
            )
            # Run directly without the interactive menu
            include_mc = not args.no_monte_carlo
            result = _run_project(
                dyn_project,
                output_dir       = output_dir,
                dry_run          = args.dry_run,
                include_monte_carlo = include_mc,
                mc_cycles        = args.mc_cycles,
                config_overrides = config_overrides,
            )
            if result:
                logger.info("  Generated file: %s", result)
            return 0
        except SimulatorError as exc:
            logger.error("Extraction error: %s", exc)
            return 1

    # ── Project selection ─────────────────────────────────────────────────────
    try:
        key, proj = _select_project(args.project)
    except KeyboardInterrupt:
        logger.info("\nAborted by user.")
        return 130

    # ── Auto-fit ──────────────────────────────────────────────────────────────
    if args.fit:
        logger.info("")
        logger.info("  Auto-fitting micro-costs to bench data ...")
        for pkey, pdef in sorted(PROJECTS.items()):
            if not pdef.reference_wcs:
                logger.info("    [%s] No bench reference, skipping fit.", pkey)
                continue
            old_costs = get_project_costs(pkey, pdef.default_config)
            old_rmse = compute_rmse(
                pdef.default_config, old_costs, pdef.reference_wcs,
            )
            fit_result = auto_fit(
                pdef.default_config, old_costs, pdef.reference_wcs,
            )
            new_costs = fit_result.costs
            new_rmse = fit_result.rmse_after
            PROJECT_COSTS[pkey] = new_costs
            logger.info(
                "    [%s] RMSE: %.1f -> %.1f \u00b5s  (%d iters, %s)",
                pkey, old_rmse, new_rmse, fit_result.iterations,
                "converged" if fit_result.converged else "NOT converged",
            )

            logger.info("    %-33s %10s", "Parameter", "Value")
            logger.info("    %s", "-" * 45)
            for fname in sorted(vars(new_costs)):
                if fname.startswith("t_"):
                    logger.info(
                        "    %-33s %10.3f", fname, getattr(new_costs, fname),
                    )
        logger.info("")

    # ── Run simulation(s) ─────────────────────────────────────────────────────
    include_mc = not args.no_monte_carlo
    saved_files: List[str] = []

    try:
        if key == "ALL":
            for pkey in sorted(PROJECTS.keys()):
                result = _run_project(
                    PROJECTS[pkey],
                    output_dir=output_dir,
                    dry_run=args.dry_run,
                    include_monte_carlo=include_mc,
                    mc_cycles=args.mc_cycles,
                    config_overrides=config_overrides,
                )
                if result:
                    saved_files.append(result)
        else:
            assert proj is not None
            result = _run_project(
                proj,
                output_dir=output_dir,
                dry_run=args.dry_run,
                include_monte_carlo=include_mc,
                mc_cycles=args.mc_cycles,
                config_overrides=config_overrides,
            )
            if result:
                saved_files.append(result)
    except SimulatorError as exc:
        logger.error("Simulation error: %s", exc)
        return 1
    except KeyboardInterrupt:
        logger.info("\nAborted by user.")
        return 130

    # ── Key Differences Summary ───────────────────────────────────────────────
    c12 = PROJECT_COSTS.get("PROJ2", COSTS_PROJ2)
    c13 = PROJECT_COSTS.get("PROJ3", COSTS_PROJ3)
    delta_displace = c13.t_l1a_per_event_displace - c12.t_l1a_per_event_displace
    logger.info("")
    logger.info("=" * 78)
    logger.info(
        "  KEY DIFFERENCES EXPLAINING PROJ3 > PROJ2 IN SCENARIOS 1 & 3",
    )
    logger.info("=" * 78)
    logger.info(
        "  1. t_l1a_per_event_displace  (PROJ2: %.1f \u00b5s vs PROJ3: %.1f \u00b5s)",
        c12.t_l1a_per_event_displace, c13.t_l1a_per_event_displace,
    )
    logger.info(
        "     -> 20 calls x %.1f \u00b5s extra = %.0f \u00b5s extra",
        delta_displace, 20 * delta_displace,
    )
    logger.info(
        "  2. t_storefrf_full_shift     (PROJ2: %.1f \u00b5s vs PROJ3: %.1f \u00b5s)",
        c12.t_storefrf_full_shift, c13.t_storefrf_full_shift,
    )
    logger.info(
        "  3. t_deferred_base           (PROJ2: %.1f \u00b5s vs PROJ3: %.1f \u00b5s)",
        c12.t_deferred_base, c13.t_deferred_base,
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("  Generated files:")
    for f in saved_files:
        logger.info("    * %s", f)
    if not saved_files:
        logger.info("    (none — dry-run or no output)")
    logger.info("=" * 60)
    logger.info("")

    return 0


if __name__ == "__main__":
    sys.exit(main())
