"""Built-in self-tests for validating simulation invariants."""

from __future__ import annotations

import logging

from dem_simulator.config import ProjectConfig, FrfBlockConfig
from dem_simulator.extractor import discover_projects as _discover_projects
from dem_simulator.costs import MicroCosts, PROJECT_COSTS
from dem_simulator.scenarios import build_scenarios
from dem_simulator.engine import DemMainFunctionSimulator
from dem_simulator.simulation import compute_rmse
from dem_simulator.exceptions import ConfigValidationError

logger = logging.getLogger("dem_simulator")


def run_self_tests() -> bool:
    """Run built-in validation tests.  Returns True if all pass.

    Tests cover:

    1. Monotonicity: increasing NrClcFmyEveAsyn must not decrease WCS time.
    2. Determinism: same inputs produce identical outputs.
    3. Non-negativity: all simulated costs must be >= 0.
    4. Bounds: simulated values must be within reasonable limits.
    5. RMSE regression: fitted costs must achieve RMSE < 20 us.
    6. Config validation catches bad inputs.
    """
    logger.info("=" * 60)
    logger.info("  SELF-TEST: Validating simulation invariants")
    logger.info("=" * 60)

    all_passed = True
    test_count = 0
    pass_count = 0

    # Descoperim proiectele din structura standard de directoare
    import os
    _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PROJECTS = _discover_projects(_base)

    def _check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal all_passed, test_count, pass_count
        test_count += 1
        status = "PASS" if condition else "FAIL"
        if not condition:
            all_passed = False
        else:
            pass_count += 1
        msg = f"  [{status}] {name}"
        if detail:
            msg += f"  ({detail})"
        logger.info(msg)

    for proj_key, proj_def in PROJECTS.items():
        cfg = proj_def.default_config
        costs = PROJECT_COSTS.get(proj_key, MicroCosts())
        sim = DemMainFunctionSimulator(cfg, costs)
        proj_scenarios = build_scenarios(
            nr_inject_first=cfg.nr_inject_first,
            nr_inject_next=cfg.nr_inject_next,
            nr_fmy=cfg.NrFmy,
        )
        proj_calibrations = proj_def.calibrations

        # Test 1: Determinism
        t1 = sim.simulate_total(proj_scenarios[0], 20, 10)
        t2 = sim.simulate_total(proj_scenarios[0], 20, 10)
        _check(f"{proj_key}: Determinism", t1 == t2, f"{t1} == {t2}")

        # Test 2: Non-negativity
        for scenario in proj_scenarios:
            for asyn, post in proj_calibrations:
                bd = sim.simulate(scenario, asyn, post)
                all_positive = all(v >= 0 for v in bd.values())
                total = sum(bd.values())
                _check(
                    f"{proj_key}: Non-negative {scenario.name} ({asyn}/{post})",
                    all_positive and total >= 0,
                    f"total={total:.1f}",
                )

        # Test 3: Monotonicity for displacement scenario (S1)
        s1 = proj_scenarios[0]
        vals = [sim.simulate_total(s1, ea, 10) for ea in [5, 10, 20]]
        _check(
            f"{proj_key}: Monotonicity S1 vs EveAsyn",
            vals[0] <= vals[1] <= vals[2],
            f"EA=5:{vals[0]:.0f} EA=10:{vals[1]:.0f} EA=20:{vals[2]:.0f}",
        )

        # Test 4: Scenario 2 (no displacement) should be cheapest
        s2_val = sim.simulate_total(proj_scenarios[1], 20, 10)
        s1_val = sim.simulate_total(proj_scenarios[0], 20, 10)
        s3_val = sim.simulate_total(proj_scenarios[2], 20, 10)
        _check(
            f"{proj_key}: S2 <= S1 and S2 <= S3",
            s2_val <= s1_val and s2_val <= s3_val,
            f"S1={s1_val:.0f} S2={s2_val:.0f} S3={s3_val:.0f}",
        )

        # Test 5: Reasonable bounds (0 < total < 5000 us)
        max_total = sim.simulate_total(proj_scenarios[0], 40, 20)
        _check(
            f"{proj_key}: Reasonable bounds",
            0 < max_total < 5000,
            f"max_total={max_total:.0f}",
        )

        # Test 6: RMSE regression against bench data
        ref = proj_def.reference_wcs
        if ref:
            rmse = compute_rmse(cfg, costs, ref, proj_calibrations)
            _check(
                f"{proj_key}: RMSE < 20 us",
                rmse < 20.0,
                f"RMSE={rmse:.1f} us",
            )

    # Test 7: Config validation catches bad inputs
    try:
        _bad = ProjectConfig(
            name="BAD", NrFmy=-1, NrFifoBas=0, NrFifoIntm=0, NrFifoRsv=0,
            NrClcFmyEveAsyn=1, NrClcFmyPost=1, NrEve=0,
            NrFrfDataTot=0, NrFrfPreData=0, NrBlockFrf=0, NrFrfPre=0,
            NrByteFrfFmy=0,
        )
        _check("Config validation rejects NrFmy=-1", False)
    except ConfigValidationError:
        _check("Config validation rejects NrFmy=-1", True)

    # Test 8: FrfBlockConfig validation
    try:
        _bad_blk = FrfBlockConfig(
            NrByteFrame=10, NrFrfIdxCalMax=5, NrIdxPerClass=5,
            NrFrfHold=5, NrFrfTot=3, LfOptions=0,  # Hold > Tot
        )
        _check("FRF block validation rejects Hold>Tot", False)
    except ConfigValidationError:
        _check("FRF block validation rejects Hold>Tot", True)

    logger.info("-" * 60)
    logger.info("  Self-test result: %d / %d passed", pass_count, test_count)
    logger.info("=" * 60)

    return all_passed
