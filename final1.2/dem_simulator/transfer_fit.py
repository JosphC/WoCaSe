"""Transfer-learning fitter for new DEM projects.

Strategy
--------
PROJ2 and PROJ3 are the reference projects with precisely calibrated costs.
(Note: project codes in this module are anonymized for licensing purposes;
the numeric values remain the ones calibrated on real data.)
For a new project (e.g. PROJ6, VWPQ3, etc.) running on a similar ECU but
possibly with:

    * Different calibrations (EveAsyn / Post with other values)
    * Extra function calls inside ``Icsp_Dem_MainFunction``
    * A different number of FMY / EVE / FRF blocks

you can use **transfer learning**:

    1. Identify the most structurally similar reference project
         (based on NrFmy, NrBlockFrf, cpu_clock_mhz).
    2. Start auto-fit from that project's costs (not from zero).
    3. ``t_main_fixed`` automatically absorbs any unknown extra functions.
    4. The remaining costs are adjusted by coordinate descent.

Usage
-----
        # Without bench data (pure transfer estimate):
        from dem_simulator.transfer_fit import infer_costs_for_project
        costs = infer_costs_for_project(new_project_config)

        # With bench data (full fit):
        from dem_simulator.transfer_fit import transfer_fit
        result = transfer_fit(new_project_config, bench_data)
        costs = result.costs
        print(f"RMSE: {result.rmse_after:.2f} µs  ({result.iterations} iterations)")

        # Add to PROJECT_COSTS for permanent use:
        from dem_simulator.costs import PROJECT_COSTS
        PROJECT_COSTS["PROJ6"] = costs
"""

from __future__ import annotations

import copy
import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from dem_simulator.config import ProjectConfig, FrfBlockConfig
from dem_simulator.costs import (
    MicroCosts,
    PROJECT_COSTS,
    COSTS_PROJ3,
)
from dem_simulator.simulation import auto_fit, compute_rmse, FitResult

logger = logging.getLogger("dem_simulator")


# ==============================================================================
# Structural similarity metric
# ==============================================================================

# Normalisation constants applied to each dimension before computing the
# Euclidean distance.  Picked to make a typical project shift ≈ 1 unit so
# distances stay easy to reason about (0 = identical, 1 ≈ one project apart,
# > 2 = very different).
_DISTANCE_NORM: Dict[str, float] = {
    "NrFmy":         20.0,
    "NrBlockFrf":     4.0,
    "NrFrfDataTot":  60.0,
    "NrEve":        200.0,
    "cpu_clock_mhz": 300.0,
    "NrCore":         2.0,
    "NrClient":       6.0,
    "NrPtuProfiles":  2.0,
}


def _structural_distance(cfg_a: ProjectConfig, cfg_b: ProjectConfig) -> float:
    """Normalised Euclidean distance between two DEM configurations.

    A small distance (≲ 0.3) usually means the same micro-cost set is a
    sensible starting point; a large distance (≳ 1.0) signals that a
    full bench fit will be required for good accuracy.
    """
    dist_sq = 0.0
    for fname, norm in _DISTANCE_NORM.items():
        va = float(getattr(cfg_a, fname, 0))
        vb = float(getattr(cfg_b, fname, 0))
        dist_sq += ((va - vb) / norm) ** 2

    # IsSharedCore / has_prio_obd_uds_swap — binary dimensions
    for flag in ("IsSharedCore", "has_prio_obd_uds_swap"):
        fa = 1.0 if getattr(cfg_a, flag, False) else 0.0
        fb = 1.0 if getattr(cfg_b, flag, False) else 0.0
        dist_sq += (fa - fb) ** 2

    return math.sqrt(dist_sq)


# ==============================================================================
# Reference catalogue (hardcoded baseline) + dynamic enrichment from bench_store
# ==============================================================================

def _frf(n_byte, idx, idx_class, hold, total):
    return FrfBlockConfig(
        NrByteFrame=n_byte, NrFrfIdxCalMax=idx, NrIdxPerClass=idx_class,
        NrFrfHold=hold, NrFrfTot=total, LfOptions=0,
    )


_PROJ_FRF = [
    _frf(48, 6, 6, 2, 8), _frf(32, 4, 4, 2, 6),
    _frf(24, 3, 3, 1, 4), _frf(16, 2, 2, 1, 3),
]
_PROJ4_FRF = [
    _frf(96, 8, 8, 2, 10), _frf(64, 6, 6, 2, 8),
    _frf(48, 4, 4, 1, 6),  _frf(32, 3, 3, 1, 4),
]


# Hard-coded baseline references — always available even without bench_store.
_BASELINE_REPRESENTATIVE_CFGS: Dict[str, ProjectConfig] = {
    "PROJ2": ProjectConfig(
        name="PROJ2", NrFmy=12, NrFifoBas=4, NrFifoIntm=8, NrFifoRsv=0,
        NrClcFmyEveAsyn=20, NrClcFmyPost=10, NrEve=150,
        NrFrfDataTot=48, NrFrfPreData=0, NrBlockFrf=4,
        NrFrfPre=6, NrByteFrfFmy=48, NrLamp=2, cpu_clock_mhz=300.0,
        FrfBlocks=_PROJ_FRF,
    ),
    "PROJ3": ProjectConfig(
        name="PROJ3", NrFmy=12, NrFifoBas=4, NrFifoIntm=8, NrFifoRsv=0,
        NrClcFmyEveAsyn=20, NrClcFmyPost=10, NrEve=200,
        NrFrfDataTot=48, NrFrfPreData=0, NrBlockFrf=4,
        NrFrfPre=6, NrByteFrfFmy=48, NrLamp=3, cpu_clock_mhz=300.0,
        FrfBlocks=_PROJ_FRF,
    ),
    "PROJ4_0U0_000": ProjectConfig(
        name="PROJ4_0U0_000", NrFmy=36, NrFifoBas=12, NrFifoIntm=24, NrFifoRsv=0,
        NrClcFmyEveAsyn=20, NrClcFmyPost=10, NrEve=400,
        NrFrfDataTot=144, NrFrfPreData=0, NrBlockFrf=4,
        NrFrfPre=10, NrByteFrfFmy=96, NrLamp=3, cpu_clock_mhz=300.0,
        NrCore=2, IsSharedCore=True,
        FrfBlocks=_PROJ4_FRF,
    ),
}


def _collect_reference_catalogue() -> Tuple[Dict[str, ProjectConfig], Dict[str, MicroCosts]]:
    """Merge baseline + bench_store data into a single ``(cfgs, costs)`` pair.

    Bench-store entries override the baseline when keys collide, so the
    catalogue reflects the most up-to-date measurements available on the
    machine.  Errors querying the store are downgraded to debug logs so
    transfer-learning still works offline.
    """
    cfgs: Dict[str, ProjectConfig] = dict(_BASELINE_REPRESENTATIVE_CFGS)
    costs: Dict[str, MicroCosts] = dict(PROJECT_COSTS)

    try:
        from dem_simulator.bench_store import (
            _ensure_seeded,
            get_all_configs,
            get_all_fitted_costs,
        )
        _ensure_seeded()
        for k, v in get_all_configs().items():
            cfgs[k.upper()] = v
        for k, v in get_all_fitted_costs().items():
            costs[k.upper()] = v
    except Exception as exc:
        logger.debug("[transfer_fit] bench_store unavailable: %s", exc)

    return cfgs, costs


# ==============================================================================
# Reference selection
# ==============================================================================

def find_closest_reference(
    cfg: ProjectConfig,
    candidates: Optional[Dict[str, MicroCosts]] = None,
) -> Tuple[str, MicroCosts, float]:
    """Locate the structurally closest reference for *cfg*.

    The catalogue is built from both the hardcoded baseline projects and
    everything currently stored in :mod:`bench_store`.  The closest entry
    that has BOTH a config and a cost set wins.
    """
    cfgs, costs_table = _collect_reference_catalogue()
    if candidates is not None:
        # Restrict to caller-provided candidates only (legacy API)
        costs_table = {k: v for k, v in costs_table.items() if k in candidates}

    best_name = "PROJ3"
    best_costs = COSTS_PROJ3
    best_dist = float("inf")

    for name, ref_cfg in cfgs.items():
        if name not in costs_table:
            continue
        dist = _structural_distance(cfg, ref_cfg)
        logger.debug(
            "  structural distance %s → %s: %.4f", cfg.name, name, dist,
        )
        if dist < best_dist:
            best_dist = dist
            best_name = name
            best_costs = costs_table[name]

    logger.info(
        "[%s] closest reference: %s (distance=%.4f)",
        cfg.name, best_name, best_dist,
    )
    return best_name, best_costs, best_dist


def find_k_nearest_references(
    cfg: ProjectConfig,
    k: int = 3,
    candidates: Optional[Dict[str, MicroCosts]] = None,
) -> List[Tuple[str, MicroCosts, float]]:
    """Return up to *k* nearest references sorted by ascending distance."""
    cfgs, costs_table = _collect_reference_catalogue()
    if candidates is not None:
        costs_table = {k: v for k, v in costs_table.items() if k in candidates}

    ranked: List[Tuple[str, MicroCosts, float]] = []
    for name, ref_cfg in cfgs.items():
        if name not in costs_table:
            continue
        ranked.append((name, costs_table[name], _structural_distance(cfg, ref_cfg)))
    ranked.sort(key=lambda t: t[2])
    return ranked[: max(1, k)]


# ==============================================================================
# CPU clock scaling (selective)
# ==============================================================================

def scale_costs_by_clock(
    costs: MicroCosts,
    source_mhz: float,
    target_mhz: float,
) -> MicroCosts:
    """Rescale CPU-bound costs by the clock ratio.

    Only the fields listed in :data:`MicroCosts.CPU_BOUND_FIELDS` are
    rescaled — memory / IO / IRQ overheads (NVM writes, cache misses,
    interrupt jitter) do not scale linearly with CPU frequency, so
    blindly scaling everything (the old behaviour) inflated those costs
    on slower targets and corrupted the transfer-learning seed.
    """
    if abs(source_mhz - target_mhz) < 1.0:
        return copy.deepcopy(costs)

    factor = source_mhz / target_mhz
    scaled = copy.deepcopy(costs)
    for fname in scaled.tunable_fields():
        if not MicroCosts.is_cpu_bound(fname):
            continue
        scaled_val = getattr(scaled, fname) * factor
        setattr(scaled, fname, MicroCosts.clamp(fname, scaled_val))

    logger.info(
        "Scaled CPU-bound costs by factor %.3f (%g MHz → %g MHz, %d fields)",
        factor, source_mhz, target_mhz, len(MicroCosts.CPU_BOUND_FIELDS),
    )
    return scaled


# ==============================================================================
# Multi-reference blending
# ==============================================================================

def _blend_costs(
    refs: List[Tuple[str, MicroCosts, float]],
    target_mhz: float,
    source_mhz: float,
) -> MicroCosts:
    """Blend the top-k nearest references with inverse-distance weighting.

    ``w_i = 1 / (d_i + ε)``  →  normalised so they sum to 1.
    Each reference is CPU-rescaled to *target_mhz* before blending, so a
    600-MHz blended seed is built from 600-MHz-equivalent rescaled
    references.

    Falls back to a deepcopy of the single nearest reference if only one
    candidate is available.
    """
    if not refs:
        return MicroCosts()

    rescaled = [
        (name, scale_costs_by_clock(c, source_mhz, target_mhz), d)
        for name, c, d in refs
    ]
    if len(rescaled) == 1:
        return rescaled[0][1]

    eps = 0.05
    weights = [1.0 / (d + eps) for _n, _c, d in rescaled]
    total_w = sum(weights) or 1.0
    weights = [w / total_w for w in weights]

    template = rescaled[0][1]
    blended = copy.deepcopy(template)
    for fname in blended.tunable_fields():
        acc = sum(getattr(c, fname) * w for (_n, c, _d), w in zip(rescaled, weights))
        setattr(blended, fname, MicroCosts.clamp(fname, acc))
    blended.p_frfpre_hit = max(
        0.0,
        min(
            1.0,
            sum(c.p_frfpre_hit * w for (_n, c, _d), w in zip(rescaled, weights)),
        ),
    )
    try:
        blended.validate()
    except Exception:
        # If validation fails (unlikely after clamping), fall back to nearest.
        blended = rescaled[0][1]
    return blended


# ==============================================================================
# Infer without bench data
# ==============================================================================

def infer_costs_for_project(
    cfg: ProjectConfig,
    source_mhz: float = 300.0,
    *,
    k: int = 3,
) -> MicroCosts:
    """Estimate costs for a new project using k-NN blending of references.

    Behaviour
    ---------
    * Pull the ``k`` nearest references from the merged catalogue (baseline
      + bench_store).
    * CPU-rescale each one to the target CPU clock.
    * Inverse-distance blend → seed costs.  This is significantly more
      robust than the old single-nearest approach when no reference is a
      close match.
    """
    refs = find_k_nearest_references(cfg, k=k)
    if not refs:
        logger.warning(
            "[%s] no reference projects available — returning defaults.",
            cfg.name,
        )
        return MicroCosts()

    seed = _blend_costs(refs, target_mhz=cfg.cpu_clock_mhz, source_mhz=source_mhz)
    best_name, _best_costs, best_dist = refs[0]
    if best_dist < 0.1:
        logger.info(
            "[%s] near-identical reference %s — costs copied directly.",
            cfg.name, best_name,
        )
    elif best_dist > 1.0:
        logger.warning(
            "[%s] best reference %s is far away (d=%.2f). "
            "Run transfer_fit() with bench data for trustworthy numbers.",
            cfg.name, best_name, best_dist,
        )
    return seed


# ==============================================================================
# Transfer fit result
# ==============================================================================

@dataclass
class TransferFitResult:
    """Result of a transfer fit.

    Attributes
    ----------
    costs : MicroCosts
        Costurile optimizate prin transfer fit.
    ref_project : str
        Reference project used as the starting point.
    structural_distance : float
        Structural distance from the reference (0 = identical).
    rmse_initial : float
        RMSE before fit, starting from the scaled reference.
    rmse_after : float
        RMSE after fit.
    iterations : int
        Number of iterations performed.
    converged : bool
        Whether the fit converged.
    per_scenario_rmse : Dict[str, float]
        RMSE per scenario after fit.
    elapsed_sec : float
        Timp total.
    notes : List[str]
        Collected notes and warnings.
    mae_after, max_abs_err_after : float
        Robust error summaries (added in v2).
    """
    costs: MicroCosts
    ref_project: str
    structural_distance: float
    rmse_initial: float
    rmse_after: float
    iterations: int
    converged: bool
    per_scenario_rmse: Dict[str, float]
    elapsed_sec: float
    notes: List[str]
    mae_after: float = 0.0
    max_abs_err_after: float = 0.0

    def summary(self) -> str:
        """Return a text summary of the results."""
        lines = [
            f"Transfer Fit — {self.ref_project} → proiect nou",
            f"  Structural distance: {self.structural_distance:.4f}",
            f"  Initial RMSE (scaled ref): {self.rmse_initial:.2f} µs",
            f"  RMSE after fit:            {self.rmse_after:.2f} µs",
            f"  MAE after fit:             {self.mae_after:.2f} µs",
            f"  MaxAE after fit:           {self.max_abs_err_after:.1f} µs",
            f"  Iterations:                {self.iterations}",
            f"  Converged:                 {'YES' if self.converged else 'NO'}",
            f"  Time:                      {self.elapsed_sec:.1f} s",
            "  RMSE per scenario:",
        ]
        for sk, rv in self.per_scenario_rmse.items():
            lines.append(f"    {sk}: {rv:.2f} µs")
        if self.notes:
            lines.append("  Notes:")
            for n in self.notes:
                lines.append(f"    ⚠ {n}")
        return "\n".join(lines)

    def print_costs_snippet(self) -> str:
        """Generate a Python snippet ready to copy into costs.py."""
        lines = [
            f"# Auto-generated by transfer_fit — add to dem_simulator/costs.py",
            f"COSTS_NEW = MicroCosts(",
        ]
        for fname in sorted(self.costs.tunable_fields()):
            val = getattr(self.costs, fname)
            lines.append(f"    {fname}={val:.4f},")
        lines.append(")")
        lines.append(f'PROJECT_COSTS["NEWPROJECT"] = COSTS_NEW  # replace NEWPROJECT')
        return "\n".join(lines)


# ==============================================================================
# Main transfer_fit function
# ==============================================================================

def transfer_fit(
    cfg: ProjectConfig,
    bench: Dict[str, List[int]],
    *,
    source_mhz: float = 300.0,
    max_iterations: int = 200,
    convergence_threshold: float = 0.005,
    verbose: bool = True,
    calibrations: Optional[Tuple[Tuple[int, int], ...]] = None,
    k_neighbors: int = 3,
) -> TransferFitResult:
    """Fit costs for a new project starting from a blended k-NN seed.

    Improvements over the legacy version
    ------------------------------------
    * **k-NN blended seed** — instead of using a single nearest reference,
      the top ``k_neighbors`` projects are inverse-distance averaged and
      CPU-rescaled.  Better when no single reference is structurally
      close.
    * **Calibrations are propagated** to ``auto_fit`` so non-default bench
      ``(eve_asyn, post)`` schedules are honoured.
    * **Robust loss is on by default** in ``auto_fit`` — outliers and
      per-scenario imbalance can no longer dominate the descent.
    """
    import time
    t_start = time.monotonic()
    notes: List[str] = []

    logger.info("=" * 60)
    logger.info("  TRANSFER FIT: %s", cfg.name)
    logger.info("=" * 60)

    # --- 1. k-NN seed --------------------------------------------------
    refs = find_k_nearest_references(cfg, k=k_neighbors)
    ref_name, _ref_costs, dist = refs[0] if refs else ("PROJ3", COSTS_PROJ3, float("inf"))

    if dist > 0.7:
        msg = (
            f"Large structural distance ({dist:.3f}) from {ref_name}. "
            "Blended seed will be used but fit may need more iterations."
        )
        notes.append(msg)
        logger.warning(msg)

    initial_costs = _blend_costs(refs, target_mhz=cfg.cpu_clock_mhz, source_mhz=source_mhz)

    rmse_initial = compute_rmse(cfg, initial_costs, bench, calibrations)
    if verbose:
        logger.info(
            "[%s] RMSE after blended seed: %.2f µs",
            cfg.name, rmse_initial,
        )

    if rmse_initial > 250.0:
        msg = (
            f"High initial RMSE ({rmse_initial:.1f} µs) — the project is "
            "structurally far from all known references. Verify cpu_clock_mhz "
            "and the FrfBlocks geometry."
        )
        notes.append(msg)
        logger.warning(msg)

    # --- 2. auto_fit ---------------------------------------------------
    if verbose:
        logger.info(
            "[%s] running auto_fit (max %d iters per pass)...",
            cfg.name, max_iterations,
        )

    fit: FitResult = auto_fit(
        cfg,
        initial_costs,
        bench,
        calibrations=calibrations,
        max_iterations=max_iterations,
        convergence_threshold=convergence_threshold,
        use_robust_loss=True,
    )

    elapsed = time.monotonic() - t_start

    if verbose:
        logger.info(
            "[%s] Fit done: RMSE %.2f → %.2f µs  MAE=%.2f  MaxAE=%.0f  "
            "(%d iters, touched=%d, %.1f s)",
            cfg.name, rmse_initial, fit.rmse_after,
            fit.mae_after, fit.max_abs_err_after,
            fit.iterations, len(fit.fields_touched), elapsed,
        )
        for sk, rv in fit.per_scenario_rmse.items():
            logger.info("  %s RMSE: %.2f µs", sk, rv)

    if fit.rmse_after > 30.0:
        notes.append(
            f"Final RMSE {fit.rmse_after:.1f} µs exceeds 30 µs target. "
            "Possible causes: bench outliers, missing functions in engine, "
            "or insufficient calibration coverage."
        )

    result = TransferFitResult(
        costs               = fit.costs,
        ref_project         = ref_name,
        structural_distance = dist,
        rmse_initial        = rmse_initial,
        rmse_after          = fit.rmse_after,
        iterations          = fit.iterations,
        converged           = fit.converged,
        per_scenario_rmse   = fit.per_scenario_rmse,
        elapsed_sec         = elapsed,
        notes               = notes,
        mae_after           = fit.mae_after,
        max_abs_err_after   = fit.max_abs_err_after,
    )

    logger.info("=" * 60)
    return result

