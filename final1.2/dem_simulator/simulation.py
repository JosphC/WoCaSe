"""WCS grid simulation, RMSE computation, and auto-fit (coordinate descent)."""

from __future__ import annotations

import copy
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from dem_simulator.constants import (
    FIT_MAX_ITERATIONS,
    FIT_CONVERGENCE_THRESHOLD,
    FIT_DELTA_FRACTIONS,
)
from dem_simulator.config import ProjectConfig
from dem_simulator.costs import MicroCosts
from dem_simulator.scenarios import Scenario, WCS_SCENARIO_KEYS, build_scenarios
from dem_simulator.config import DEFAULT_CALIBRATIONS
from dem_simulator.engine import DemMainFunctionSimulator

logger = logging.getLogger("dem_simulator")


# ==============================================================================
# Internal helpers
# ==============================================================================

def _scenarios_for_config(cfg: ProjectConfig) -> Tuple[Scenario, ...]:
    """Build WCS scenarios from instrumentation counts + NrFmy."""
    return build_scenarios(
        nr_inject_first=cfg.nr_inject_first,
        nr_inject_next=cfg.nr_inject_next,
        nr_fmy=cfg.NrFmy,
    )


def _iter_residuals(
    cfg: ProjectConfig,
    costs: MicroCosts,
    bench: Dict[str, List[int]],
    calibrations: Tuple[Tuple[int, int], ...],
):
    """Yield ``(scenario_key, cal_index, simulated_us, bench_us)`` tuples.

    Skips bench cells that are ``<= 0`` (missing / placeholder) and any
    calibration indices past the end of the bench row.
    """
    sim = DemMainFunctionSimulator(cfg, costs)
    scenarios = _scenarios_for_config(cfg)
    for s_idx, scenario in enumerate(scenarios):
        skey = WCS_SCENARIO_KEYS[s_idx]
        bench_row = bench.get(skey, [])
        for ci, (eve_asyn, fmy_post) in enumerate(calibrations):
            if ci >= len(bench_row):
                continue
            actual = bench_row[ci]
            if actual <= 0:
                continue
            simulated = sim.simulate_total(scenario, eve_asyn, fmy_post)
            yield skey, ci, simulated, float(actual)


# ==============================================================================
# WCS Grid Simulation
# ==============================================================================

def simulate_wcs_grid(
    cfg: ProjectConfig,
    costs: MicroCosts,
    calibrations: Optional[Tuple[Tuple[int, int], ...]] = None,
) -> Dict[str, List[float]]:
    """Run the WCS simulation for all 3 scenarios x N calibrations."""
    if calibrations is None:
        calibrations = DEFAULT_CALIBRATIONS
    sim = DemMainFunctionSimulator(cfg, costs)
    scenarios = _scenarios_for_config(cfg)
    results: Dict[str, List[float]] = {}

    for s_idx, scenario in enumerate(scenarios):
        skey = WCS_SCENARIO_KEYS[s_idx]
        row: List[float] = []
        for nr_asyn, nr_post in calibrations:
            t_us = sim.simulate_total(scenario, nr_asyn, nr_post)
            row.append(round(t_us))
        results[skey] = row

    return results


# ==============================================================================
# Loss functions
# ==============================================================================

def _huber(residual: float, delta: float) -> float:
    """Huber loss — quadratic for |r| < δ, linear afterwards.

    Reduces the influence of bench outliers (e.g. a single rogue
    measurement of 1968 µs when the rest sit around 400) without ignoring
    them completely.
    """
    r = abs(residual)
    if r <= delta:
        return 0.5 * r * r
    return delta * (r - 0.5 * delta)


def _huber_delta(residuals: Sequence[float], default: float = 60.0) -> float:
    """Robust δ ≈ 1.345 · MAD / 0.6745 (consistent with N(0,1))."""
    if not residuals:
        return default
    sorted_abs = sorted(abs(r) for r in residuals)
    median_abs = sorted_abs[len(sorted_abs) // 2]
    mad = max(median_abs, 1.0)
    return max(20.0, min(200.0, 1.345 * mad / 0.6745))


def detect_outliers(
    project: ProjectConfig,
    costs: MicroCosts,
    bench: Dict[str, List[int]],
    calibrations: Optional[Tuple[Tuple[int, int], ...]] = None,
    *,
    sigma_threshold: float = 4.0,
) -> List[Tuple[str, int, float, float, float]]:
    """Flag bench cells whose residual is > *sigma_threshold* · MAD.

    Returns
    -------
    list of (scenario_key, cal_index, bench_us, simulated_us, residual_us)
        Cells marked as outliers — these are typically the result of a
        bench measurement glitch (e.g. a 1968 µs reading in a column
        whose neighbours sit around 400 µs).
    """
    if calibrations is None:
        calibrations = DEFAULT_CALIBRATIONS

    samples: List[Tuple[str, int, float, float, float]] = []
    for skey, ci, simulated, actual in _iter_residuals(project, costs, bench, calibrations):
        samples.append((skey, ci, float(actual), float(simulated), simulated - actual))

    if len(samples) < 4:
        return []

    residuals = [s[4] for s in samples]
    sorted_abs = sorted(abs(r) for r in residuals)
    median_abs = sorted_abs[len(sorted_abs) // 2]
    mad = max(median_abs, 1.0)
    threshold = sigma_threshold * mad

    return [s for s in samples if abs(s[4]) > threshold]


def _build_bench_mask(
    project: ProjectConfig,
    costs: MicroCosts,
    bench: Dict[str, List[int]],
    calibrations: Tuple[Tuple[int, int], ...],
    *,
    sigma_threshold: float = 4.0,
) -> Dict[Tuple[str, int], bool]:
    """Return ``{(scenario, cal_index): keep}`` excluding flagged outliers."""
    flagged = detect_outliers(
        project, costs, bench, calibrations, sigma_threshold=sigma_threshold
    )
    excluded = {(s[0], s[1]) for s in flagged}
    mask: Dict[Tuple[str, int], bool] = {}
    for skey, ci, _sim, _act in _iter_residuals(project, costs, bench, calibrations):
        mask[(skey, ci)] = (skey, ci) not in excluded
    return mask


def _masked_bench(
    bench: Dict[str, List[int]],
    mask: Dict[Tuple[str, int], bool],
) -> Dict[str, List[int]]:
    """Return a copy of *bench* with masked-out cells set to 0 (== skip)."""
    out: Dict[str, List[int]] = {}
    for skey, row in bench.items():
        new_row: List[int] = []
        for ci, v in enumerate(row):
            if mask.get((skey, ci), True):
                new_row.append(v)
            else:
                new_row.append(0)  # 0 = treated as "missing" downstream
        out[skey] = new_row
    return out


# ==============================================================================
# RMSE / MAE / Huber computation
# ==============================================================================


def compute_rmse(
    project: ProjectConfig,
    costs: MicroCosts,
    bench: Dict[str, List[int]],
    calibrations: Optional[Tuple[Tuple[int, int], ...]] = None,
) -> float:
    """Composite loss: sum of per-scenario RMSEs (ensures every scenario fits)."""
    per_scenario = compute_per_scenario_rmse(project, costs, bench, calibrations)
    return sum(per_scenario.values())


def compute_per_scenario_rmse(
    project: ProjectConfig,
    costs: MicroCosts,
    bench: Dict[str, List[int]],
    calibrations: Optional[Tuple[Tuple[int, int], ...]] = None,
) -> Dict[str, float]:
    """Compute RMSE separately for each scenario."""
    if calibrations is None:
        calibrations = DEFAULT_CALIBRATIONS
    err_sq: Dict[str, float] = {k: 0.0 for k in WCS_SCENARIO_KEYS}
    counts: Dict[str, int] = {k: 0 for k in WCS_SCENARIO_KEYS}
    for skey, _ci, simulated, actual in _iter_residuals(project, costs, bench, calibrations):
        err_sq[skey] += (simulated - actual) ** 2
        counts[skey] += 1
    return {
        k: math.sqrt(err_sq[k] / counts[k]) if counts[k] > 0 else 0.0
        for k in WCS_SCENARIO_KEYS
    }


def compute_error_metrics(
    project: ProjectConfig,
    costs: MicroCosts,
    bench: Dict[str, List[int]],
    calibrations: Optional[Tuple[Tuple[int, int], ...]] = None,
    *,
    huber_delta: Optional[float] = None,
) -> Dict[str, float]:
    """Return a dict with composite ``rmse``, ``mae``, ``max_abs_err`` and
    ``huber_loss`` for the given project / costs vs bench.

    ``huber_delta`` is derived automatically from the residuals when None.
    """
    if calibrations is None:
        calibrations = DEFAULT_CALIBRATIONS

    residuals: List[float] = []
    for _skey, _ci, simulated, actual in _iter_residuals(
        project, costs, bench, calibrations
    ):
        residuals.append(simulated - actual)

    n = len(residuals)
    if n == 0:
        return {"rmse": 0.0, "mae": 0.0, "max_abs_err": 0.0, "huber_loss": 0.0}

    rmse = math.sqrt(sum(r * r for r in residuals) / n)
    mae = sum(abs(r) for r in residuals) / n
    max_ae = max(abs(r) for r in residuals)
    delta = huber_delta if huber_delta is not None else _huber_delta(residuals)
    huber_loss = sum(_huber(r, delta) for r in residuals) / n

    return {
        "rmse": rmse,
        "mae": mae,
        "max_abs_err": max_ae,
        "huber_loss": huber_loss,
        "huber_delta": delta,
    }


def compute_loss(
    project: ProjectConfig,
    costs: MicroCosts,
    bench: Dict[str, List[int]],
    calibrations: Optional[Tuple[Tuple[int, int], ...]] = None,
    *,
    huber_delta: Optional[float] = None,
    scenario_weights: Optional[Dict[str, float]] = None,
) -> float:
    """Robust fit loss: per-scenario weighted average of Huber loss.

    * Huber loss caps the contribution of bench outliers so a single
      mismeasured cell cannot dominate the descent.
    * Weighting per scenario keeps S1 (the published WCS) from being
      drowned by S2/S3, which usually have more samples but lower stakes.
    """
    if calibrations is None:
        calibrations = DEFAULT_CALIBRATIONS

    if scenario_weights is None:
        # S1 is the published worst-case scenario — weight it slightly more
        # so the fitter never sacrifices S1 accuracy for S2/S3.
        scenario_weights = {"scenario_1": 1.5, "scenario_2": 1.0, "scenario_3": 1.0}

    # Collect residuals per scenario for adaptive Huber δ.
    residuals_per_scn: Dict[str, List[float]] = {k: [] for k in WCS_SCENARIO_KEYS}
    for skey, _ci, simulated, actual in _iter_residuals(
        project, costs, bench, calibrations
    ):
        residuals_per_scn[skey].append(simulated - actual)

    delta = huber_delta if huber_delta is not None else _huber_delta(
        [r for rs in residuals_per_scn.values() for r in rs]
    )

    total = 0.0
    total_w = 0.0
    for skey, rs in residuals_per_scn.items():
        if not rs:
            continue
        w = scenario_weights.get(skey, 1.0)
        mean_huber = sum(_huber(r, delta) for r in rs) / len(rs)
        total += w * mean_huber
        total_w += w
    return total / total_w if total_w > 0 else 0.0


# ==============================================================================
# FitResult + auto_fit
# ==============================================================================

@dataclass
class FitResult:
    """Result of the auto-fit procedure."""
    costs: MicroCosts
    rmse_before: float
    rmse_after: float
    iterations: int
    converged: bool
    per_scenario_rmse: Dict[str, float]
    elapsed_sec: float
    # New diagnostic metrics (added by auto_fit v2)
    mae_after: float = 0.0
    max_abs_err_after: float = 0.0
    huber_loss_after: float = 0.0
    fields_touched: List[str] = field(default_factory=list)
    outliers: List[Tuple[str, int, float, float, float]] = field(default_factory=list)
    # Same metrics computed *excluding* the detected outliers — useful to
    # report the "clean-bench" accuracy alongside the headline numbers.
    rmse_after_clean: float = 0.0
    mae_after_clean: float = 0.0
    max_abs_err_after_clean: float = 0.0


def simulate_with_breakdown(
    cfg: ProjectConfig,
    costs: MicroCosts,
    scenario: Scenario,
    nr_clc_fmy_eve_asyn: int,
    nr_clc_fmy_post: int,
) -> Dict[str, Dict[str, float]]:
    """Return detailed per-phase breakdown with percentage shares."""
    sim = DemMainFunctionSimulator(cfg, costs)
    phase_us = sim.simulate(scenario, nr_clc_fmy_eve_asyn, nr_clc_fmy_post)
    total_us = sum(phase_us.values())
    if total_us <= 0:
        phase_share_pct = {k: 0.0 for k in phase_us}
    else:
        phase_share_pct = {k: (v / total_us) * 100.0 for k, v in phase_us.items()}
    return {
        "phase_us": phase_us,
        "phase_share_pct": phase_share_pct,
        "total_us": {"value": total_us},
    }


# ------------------------------------------------------------------
#  auto_fit — robust coordinate descent
# ------------------------------------------------------------------

# Default multi-pass schedule (large → small steps).  Each pass restarts
# from the best point found so far, so the optimiser keeps making progress
# even after the early coarse passes converge.
_DEFAULT_FIT_PASSES: Tuple[Tuple[float, ...], ...] = (
    (0.30, 0.20, 0.10, -0.10, -0.20, -0.30),
    (0.10, 0.05, 0.02, -0.02, -0.05, -0.10),
    (0.04, 0.02, 0.01, -0.01, -0.02, -0.04),
)


def auto_fit(
    project: ProjectConfig,
    costs: MicroCosts,
    bench: Dict[str, List[int]],
    *,
    calibrations: Optional[Sequence[Tuple[int, int]]] = None,
    max_iterations: int = FIT_MAX_ITERATIONS,
    convergence_threshold: float = FIT_CONVERGENCE_THRESHOLD,
    delta_fractions: Sequence[float] = FIT_DELTA_FRACTIONS,
    fit_passes: Optional[Sequence[Sequence[float]]] = None,
    use_robust_loss: bool = True,
    scenario_weights: Optional[Dict[str, float]] = None,
    exclude_outliers: bool = True,
    outlier_sigma: float = 4.0,
) -> FitResult:
    """Robust coordinate-descent optimiser.

    Improvements over the legacy version
    ------------------------------------
    * **Calibrations are honoured** — previously they were silently
      ignored, so bench data with non-default ``(eve_asyn, post)`` pairs
      produced wrong fits.
    * **Additive seeding for zero-valued fields** — fields such as
      ``t_isr_jitter`` start at 0.  A pure multiplicative descent
      (``val × (1+δ)``) can never lift them, so they stay disabled
      forever.  ``MicroCosts.ZERO_INIT_STEPS`` provides a small list of
      additive seeds (1 µs … 300 µs) tried whenever the current value is
      below ``ZERO_INIT_EPS``.
    * **Physical clamping** — every trial value is clipped into
      ``MicroCosts.BOUNDS[fname]`` to prevent non-physical optima.
    * **Multi-pass schedule** — coarse → medium → fine passes, restarting
      from the best costs found so far.  Replaces the single-pass
      ``delta_fractions`` and the "stop on first non-improvement" rule.
    * **Robust loss** — Huber + per-scenario weighting so a single
      mismeasured bench cell can't dominate the descent.
    * **Outlier exclusion** — cells with residual > *outlier_sigma* · MAD
      (computed against the *initial* fit) are masked from the descent
      and reported separately in ``FitResult.fields_touched``.

    Parameters
    ----------
    use_robust_loss : bool
        If True (default), drive the descent with the Huber composite loss
        but still report RMSE in the final result.  Set False to fall back
        to the classical RMSE-only descent (useful for back-compat tests).
    exclude_outliers : bool
        If True, automatically detect and mask bench outliers before
        running the descent.  RMSE / MAE reported in ``FitResult`` are
        computed against the full bench (outliers included) so the user
        can still see them.
    outlier_sigma : float
        MAD multiplier used by :func:`detect_outliers` (4.0 ≈ 6σ for a
        Gaussian distribution — only true measurement glitches qualify).
    fit_passes : sequence of sequence of float, optional
        Override the default schedule of `delta_fractions` per pass.
    """
    if calibrations is None:
        cals = DEFAULT_CALIBRATIONS
    else:
        cals = tuple((int(a), int(p)) for a, p in calibrations)

    if fit_passes is None:
        fit_passes = _DEFAULT_FIT_PASSES

    t_start = time.monotonic()

    # Clamp the seed into physical bounds so callers can pass legacy /
    # corrupted costs without polluting the descent.
    sanitized = copy.deepcopy(costs)
    for fname in sanitized.tunable_fields():
        setattr(sanitized, fname, MicroCosts.clamp(fname, getattr(sanitized, fname)))

    # Outlier mask: identify glitches against the sanitized seed and use
    # a masked bench for the descent only.  Reported metrics still use
    # the full bench, so users see the unfiltered error.
    if exclude_outliers:
        outliers = detect_outliers(project, sanitized, bench, cals, sigma_threshold=outlier_sigma)
        if outliers:
            logger.info(
                "[fit] %s: masking %d bench outliers (>%g·MAD): %s",
                project.name, len(outliers), outlier_sigma,
                ", ".join(f"{s}/c{i}={b:.0f}" for s, i, b, _sim, _r in outliers[:5]),
            )
        mask = _build_bench_mask(project, sanitized, bench, cals, sigma_threshold=outlier_sigma)
        bench_for_fit = _masked_bench(bench, mask)
    else:
        outliers = []
        bench_for_fit = bench

    def _loss(c: MicroCosts) -> float:
        if use_robust_loss:
            return compute_loss(
                project, c, bench_for_fit, cals,
                scenario_weights=scenario_weights,
            )
        return compute_rmse(project, c, bench_for_fit, cals)

    best = sanitized
    rmse_before = compute_rmse(project, best, bench, cals)
    best_score = _loss(best)
    tunable = best.tunable_fields()

    iteration = 0
    touched: List[str] = []
    converged = False
    ZERO_EPS = 1e-6

    for pass_idx, deltas in enumerate(fit_passes, 1):
        deltas = tuple(deltas)
        for inner in range(1, max_iterations + 1):
            iteration += 1
            improved_any = False
            prev_score = best_score

            for fname in tunable:
                current_val = getattr(best, fname)
                local_best = best
                local_best_score = best_score
                local_best_val = current_val

                # 1) Multiplicative trials around the current value.
                for delta_frac in deltas:
                    if current_val < ZERO_EPS and delta_frac > 0:
                        # Multiplicative descent cannot escape 0 — skip;
                        # the additive seeds below handle this case.
                        continue
                    trial_val = MicroCosts.clamp(
                        fname, current_val * (1.0 + delta_frac)
                    )
                    if abs(trial_val - current_val) < 1e-9:
                        continue
                    trial = copy.deepcopy(best)
                    setattr(trial, fname, trial_val)
                    score = _loss(trial)
                    if score < local_best_score - 1e-9:
                        local_best = trial
                        local_best_score = score
                        local_best_val = trial_val

                # 2) Additive seeds — only when the field is at 0 (or near 0).
                if current_val < ZERO_EPS:
                    for seed_val in MicroCosts.zero_init_steps(fname):
                        trial_val = MicroCosts.clamp(fname, seed_val)
                        trial = copy.deepcopy(best)
                        setattr(trial, fname, trial_val)
                        score = _loss(trial)
                        if score < local_best_score - 1e-9:
                            local_best = trial
                            local_best_score = score
                            local_best_val = trial_val

                if local_best_score < best_score - 1e-9:
                    best = local_best
                    best_score = local_best_score
                    improved_any = True
                    if fname not in touched:
                        touched.append(fname)

            improvement = prev_score - best_score
            logger.debug(
                "[fit] pass=%d iter=%d  loss=%.4f  (Δ=%.5f)",
                pass_idx, inner, best_score, improvement,
            )
            if not improved_any or improvement < convergence_threshold:
                logger.debug(
                    "[fit] pass %d converged at iter %d (loss=%.4f)",
                    pass_idx, inner, best_score,
                )
                break
        else:
            converged = False
            continue
        converged = True

    elapsed = time.monotonic() - t_start
    per_scenario = compute_per_scenario_rmse(project, best, bench, cals)
    metrics = compute_error_metrics(project, best, bench, cals)

    # Clean-bench metrics (outliers excluded) — only when we masked some.
    if outliers:
        clean_metrics = compute_error_metrics(project, best, bench_for_fit, cals)
    else:
        clean_metrics = metrics

    logger.info(
        "[fit] %s: RMSE %.2f → %.2f µs  MAE=%.2f  MaxAE=%.0f  "
        "(iters=%d, touched=%d/%d fields, outliers=%d, %.2fs)",
        project.name, rmse_before, metrics["rmse"], metrics["mae"],
        metrics["max_abs_err"], iteration, len(touched), len(tunable),
        len(outliers), elapsed,
    )

    return FitResult(
        costs=best,
        rmse_before=rmse_before,
        rmse_after=metrics["rmse"],
        iterations=iteration,
        converged=converged,
        per_scenario_rmse=per_scenario,
        elapsed_sec=elapsed,
        mae_after=metrics["mae"],
        max_abs_err_after=metrics["max_abs_err"],
        huber_loss_after=metrics["huber_loss"],
        fields_touched=touched,
        outliers=outliers,
        rmse_after_clean=clean_metrics["rmse"],
        mae_after_clean=clean_metrics["mae"],
        max_abs_err_after_clean=clean_metrics["max_abs_err"],
    )

