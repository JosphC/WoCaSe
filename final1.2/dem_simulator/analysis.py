"""Monte Carlo, deterministic, sensitivity, cross-variant analysis, and JSON config.

Combines the higher-level analysis functions that build on the core engine.
"""

from __future__ import annotations

import json
import logging
import math
import random
import statistics
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from dem_simulator.exceptions import SimulatorError
from dem_simulator.constants import (
    MC_DEFAULT_CYCLES,
    MC_DEFAULT_SEED,
    MC_IRQ_MU,
    MC_IRQ_SIGMA,
    SENSITIVITY_POST_VALS,
    SENSITIVITY_EA_VALS,
)
from dem_simulator.config import (
    ProjectConfig,
    ProjectDefinition,
)
from dem_simulator.extractor import _make_variant
from dem_simulator.costs import MicroCosts, PROJECT_COSTS
from dem_simulator.scenarios import Scenario, build_scenarios
from dem_simulator.engine import DemMainFunctionSimulator

logger = logging.getLogger("dem_simulator")


# ==============================================================================
# Monte Carlo
# ==============================================================================

@dataclass
class MonteCarloResult:
    """Result of a Monte-Carlo peak-runtime simulation.

    Attributes
    ----------
    peak_us, mean_us, median_us, stdev_us, min_us : float
        Summary statistics of the sampled runtimes.
    p95_us, p99_us, p999_us : float
        Percentile values.
    num_cycles : int
        Number of simulation cycles performed.
    ci95_low, ci95_high : float
        95 %% confidence interval bounds on the mean.
    elapsed_sec : float
        Wall-clock time (seconds).
    seed : int
        Random seed used (for reproducibility).
    """
    peak_us: float
    mean_us: float
    median_us: float
    stdev_us: float
    min_us: float
    p95_us: float
    p99_us: float
    p999_us: float
    num_cycles: int
    ci95_low: float
    ci95_high: float
    elapsed_sec: float
    seed: int


def _random_scenario(rng: random.Random) -> Scenario:
    """Generate a randomised scenario for Monte-Carlo runs."""
    roll = rng.random()
    if roll < 0.85:
        # Normal: 0-3 events, no displacement
        nr_first = rng.randint(0, 3)
        return Scenario(
            name="random", description="",
            nr_events_first=nr_first,
            nr_events_second=0,
            fmy_initially_full=rng.random() < 0.05,
            frf_slots_full=rng.random() < 0.05,
        )
    elif roll < 0.955:
        # Moderate burst (0.85 + 0.15*0.7 = 0.955)
        nr_first = rng.randint(3, 15)
        return Scenario(
            name="random_burst", description="",
            nr_events_first=nr_first,
            nr_events_second=0,
            fmy_initially_full=rng.random() < 0.1,
            frf_slots_full=rng.random() < 0.1,
        )
    else:
        # Rare: displacement scenario
        nr_first = rng.randint(5, 20)
        nr_second = rng.randint(5, 20)
        fmy_full = rng.random() < 0.5
        return Scenario(
            name="random_displace", description="",
            nr_events_first=0 if fmy_full else nr_first,
            nr_events_second=nr_second,
            fmy_initially_full=fmy_full,
            frf_slots_full=fmy_full,
        )


def simulate_peak_runtime(
    cfg: ProjectConfig,
    costs: MicroCosts,
    *,
    num_cycles: int = MC_DEFAULT_CYCLES,
    seed: int = MC_DEFAULT_SEED,
    irq_mu: float = MC_IRQ_MU,
    irq_sigma: float = MC_IRQ_SIGMA,
) -> MonteCarloResult:
    """Monte-Carlo simulation of ``debug_dem_highest_time``.

    Simulates *num_cycles* invocations of ``Icsp_Dem_MainFunction``
    with randomised scenario conditions and log-normal interrupt overhead.

    Parameters
    ----------
    cfg : ProjectConfig
        Project configuration.
    costs : MicroCosts
        Micro-cost model.
    num_cycles : int
        Number of simulation cycles.
    seed : int
        Random seed for reproducibility.
    irq_mu, irq_sigma : float
        Parameters for the log-normal interrupt jitter distribution.

    Returns
    -------
    MonteCarloResult
        Full statistics including confidence intervals.
    """
    t_start = time.monotonic()
    rng = random.Random(seed)
    sim = DemMainFunctionSimulator(cfg, costs)
    times: List[float] = []

    for _ in range(num_cycles):
        scenario = _random_scenario(rng)
        t = sim.simulate_total(scenario, cfg.NrClcFmyEveAsyn, cfg.NrClcFmyPost)
        # Add random interrupt overhead (log-normal)
        t += max(0.0, rng.lognormvariate(irq_mu, irq_sigma))
        times.append(t)

    times_sorted = sorted(times)
    n = len(times_sorted)
    mean_val = statistics.mean(times)
    stdev_val = statistics.stdev(times) if n > 1 else 0.0

    # 95% confidence interval on the mean
    z95 = 1.96
    ci_half = z95 * stdev_val / math.sqrt(n) if n > 0 else 0.0

    elapsed = time.monotonic() - t_start

    return MonteCarloResult(
        peak_us=max(times),
        mean_us=mean_val,
        median_us=statistics.median(times),
        stdev_us=stdev_val,
        min_us=min(times),
        p95_us=times_sorted[int(0.95 * n)] if n > 0 else 0.0,
        p99_us=times_sorted[int(0.99 * n)] if n > 0 else 0.0,
        p999_us=times_sorted[int(0.999 * n)] if n > 0 else 0.0,
        num_cycles=num_cycles,
        ci95_low=mean_val - ci_half,
        ci95_high=mean_val + ci_half,
        elapsed_sec=elapsed,
        seed=seed,
    )


# ==============================================================================
# Deterministic Scenario Analysis
# ==============================================================================

def build_deterministic_scenarios() -> List[Tuple[str, Scenario]]:
    """Return a list of ``(name, Scenario)`` tuples for key scenarios."""
    return [
        (
            "Idle (no events)",
            Scenario("Idle", "", 0, 0, False, False),
        ),
        (
            "Normal (3 events, no displacement)",
            Scenario("Normal", "", 3, 0, False, False),
        ),
        (
            "Burst (20 events fill FMY)",
            Scenario("Burst", "", 20, 0, False, False),
        ),
        (
            "Displacement burst (20+20, FMY empty)",
            Scenario("Displace", "", 20, 20, False, False),
        ),
        (
            "Full FMY displacement (20 events)",
            Scenario("FullDisplace", "", 0, 20, True, True),
        ),
    ]


# ==============================================================================
# Sensitivity Analysis
# ==============================================================================

def sensitivity_analysis(
    base_cfg: ProjectConfig,
    costs: MicroCosts,
) -> None:
    """Print how ``NrClcFmyEveAsyn`` and ``NrClcFmyPost`` affect WCS time."""
    sim = DemMainFunctionSimulator(base_cfg, costs)
    scenarios = build_scenarios(
        nr_inject_first=base_cfg.nr_inject_first,
        nr_inject_next=base_cfg.nr_inject_next,
        nr_fmy=base_cfg.NrFmy,
    )

    logger.info("Reference worst-case (Cal_1, 20/10):")
    for scenario in scenarios:
        t = sim.simulate_total(scenario, 20, 10)
        logger.info("  %s: %.1f us", scenario.name, t)

    logger.info("--- NrClcFmyEveAsyn sweep (NrClcFmyPost=10) ---")
    for ea in SENSITIVITY_EA_VALS:
        vals = []
        for scenario in scenarios:
            t = sim.simulate_total(scenario, ea, 10)
            vals.append(f"{t:.0f}")
        marker = " <-- current" if ea == base_cfg.NrClcFmyEveAsyn else ""
        logger.info(
            "  EveAsyn=%2d: S1=%5s S2=%5s S3=%5s%s",
            ea, vals[0], vals[1], vals[2], marker,
        )

    logger.info("--- NrClcFmyPost sweep (NrClcFmyEveAsyn=20) ---")
    for fp in SENSITIVITY_POST_VALS:
        vals = []
        for scenario in scenarios:
            t = sim.simulate_total(scenario, 20, fp)
            vals.append(f"{t:.0f}")
        marker = " <-- current" if fp == base_cfg.NrClcFmyPost else ""
        logger.info(
            "  Post=%2d:    S1=%5s S2=%5s S3=%5s%s",
            fp, vals[0], vals[1], vals[2], marker,
        )


# ==============================================================================
# Cross-Variant Comparison
# ==============================================================================

def cross_variant_comparison(
    costs: MicroCosts,
    project: Optional[ProjectDefinition] = None,
) -> None:
    """Compare worst-case runtime across all known PTU variants."""
    if not project or not project.variant_configs:
        logger.info("--- Cross-Variant Comparison: no variant available ---")
        return
    proj_name = project.name
    variants = project.variant_configs

    logger.info("--- Cross-Variant Comparison (%s, Cal_1 20/10) ---", proj_name)
    logger.info(
        "  %-12s %6s %6s %9s %8s %8s %8s",
        "Variant", "NrFmy", "NrEve", "NrClient", "S1(us)", "S2(us)", "S3(us)",
    )

    for name, cfg in sorted(variants.items()):
        sim = DemMainFunctionSimulator(cfg, costs)
        v_scenarios = build_scenarios(
            nr_inject_first=cfg.nr_inject_first,
            nr_inject_next=cfg.nr_inject_next,
            nr_fmy=cfg.NrFmy,
        )
        vals = []
        for scenario in v_scenarios:
            t = sim.simulate_total(scenario, cfg.NrClcFmyEveAsyn, cfg.NrClcFmyPost)
            vals.append(t)
        logger.info(
            "  %-12s %6d %6d %9d %8.0f %8.0f %8.0f",
            name, cfg.NrFmy, cfg.NrEve, cfg.NrClient,
            vals[0], vals[1], vals[2],
        )


# ==============================================================================
# External Configuration File Support (JSON)
# ==============================================================================

def load_config_from_json(path: str) -> Dict[str, Any]:
    """Load a JSON configuration file and return the parsed dict.

    Expected JSON structure::

        {
          "project_name": "PROJ3",
          "config": { <ProjectConfig fields> },
          "costs": { <MicroCosts fields> },
          "reference_wcs": { "scenario_1": [...], ... }
        }

    Raises
    ------
    SimulatorError
        If the file cannot be read or parsed.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise SimulatorError(f"Cannot load config from {path!r}: {exc}") from exc

    if not isinstance(data, dict):
        raise SimulatorError(f"Config file {path!r} must contain a JSON object")

    return data


def apply_json_config(
    data: Dict[str, Any],
    project_key: str,
    base_cfg: Optional["ProjectConfig"] = None,
) -> Tuple[Optional["ProjectConfig"], Optional[MicroCosts]]:
    """Apply overrides from a parsed JSON config to the project.

    Returns the overridden ``(ProjectConfig, MicroCosts)`` or ``(None, None)``
    if the JSON does not contain overrides for *project_key*.
    """
    if data.get("project_name", "").upper() != project_key.upper():
        return None, None

    cfg_overrides = data.get("config", {})
    cost_overrides = data.get("costs", {})

    new_cfg: Optional[ProjectConfig] = None
    new_costs: Optional[MicroCosts] = None

    if cfg_overrides and base_cfg is not None:
        new_cfg = _make_variant(base_cfg, **cfg_overrides)
        logger.info("Applied config overrides for %s from JSON", project_key)
    elif cfg_overrides:
        logger.warning(
            "JSON config overrides for %s ignored — no base_cfg provided.",
            project_key,
        )

    if cost_overrides:
        base_costs = PROJECT_COSTS.get(project_key, MicroCosts())
        merged = base_costs.to_dict()
        merged.update(cost_overrides)
        new_costs = MicroCosts.from_dict(merged)
        logger.info("Applied cost overrides for %s from JSON", project_key)

    return new_cfg, new_costs
