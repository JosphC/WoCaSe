# Simulation Model

## 1. Overview

The `dem_simulator` package implements an **analytical step-by-step model** of the `Icsp_Dem_MainFunction()` execution. The function's runtime is measured between two `Gpt_GetSystemTime()` calls on the ECU; the simulator reproduces this by accumulating micro-costs for each sub-function invoked during execution.

The model predicts the variable `debug_dem_highest_time` in microseconds (µs).

---

## 2. Target Function Structure

`Icsp_Dem_MainFunction()` processes diagnostic events through several sequential stages:

```
GetSystemTime() ─── start ───────────────────────────────────
  │
  ├── Fixed overhead (config check, ChkClrReq, WaitClrResp, TestFrfData, NVM)
  │
  ├── ClcMainTranB1         — per confirmed-threshold entry
  │
  ├── ClcMainTranL1a        — per FIFO event (new entry or displacement)
  │
  ├── ClcMainTranL1b        — per FMY entry (always NrFmy iterations)
  │
  ├── ClcMainTranLamp       — lamp debouncing
  │
  ├── ClcMain2 / ClcFrfUpd  — per deferred post-processing entry
  │     └── StoreFrf        — per FRF block per deferred entry
  │
  ├── ClcFrfPre             — per pre-stored FRF entry
  │
  ├── NVM on-fly, FrfSrv, FctPerm, FctScdn, UpdObdFrf
  │
GetSystemTime() ─── end ─────────────────────────────────────
```

---

## 3. Micro-Cost Model (`MicroCosts`)

Each elementary operation has a cost in µs. These are the **20 tunable parameters**:

| Parameter | Description | Unit |
|-----------|-------------|------|
| `t_main_fixed` | Fixed overhead of MainFunction (timer, config, ChkClrReq, etc.) | µs |
| `t_b1_per_entry` | ClcMainTranB1: cost per confirmed-threshold entry | µs |
| `t_l1a_per_event_new` | L1a: cost per FIFO event — new entry (empty slot) | µs |
| `t_l1a_per_event_displace` | L1a: cost per FIFO event — displacement (priority sort) | µs |
| `t_l1b_per_entry_empty` | L1b: cost per empty FMY slot (just check EventId) | µs |
| `t_l1b_per_entry_valid` | L1b: cost per valid FMY entry (TreatEntry logic) | µs |
| `t_l1b_resorting` | L1b: HistoryResorting if entries erased | µs |
| `t_lamp` | ClcMainTranLamp: one lamp entry | µs |
| `t_deferred_base` | ClcMain2: base cost per deferred entry | µs |
| `t_storefrf_no_update` | StoreFrf: block not requested | µs |
| `t_storefrf_free_frame` | StoreFrf: free frame available | µs |
| `t_storefrf_full_shift` | StoreFrf: all frames full → shift + rewrite | µs |
| `t_collect_per_idx` | Per NrIdxPerClass RTE data read | µs |
| `t_collect_fixed` | CollectDataForBlock fixed cost | µs |
| `t_frfpre_per_entry` | ClcFrfPre: per pre-stored FRF processed | µs |
| `t_nvm_onfly` | NVM on-fly treatment | µs |
| `t_frfsrv` | FrfSrv_GetFrfData (0 unless tester connected) | µs |
| `t_fct_perm` | FctPerm function pointer cost | µs |
| `t_fct_scdn` | FctScdn function pointer cost | µs |
| `t_upd_obd_frf` | UpdObdFrf cost | µs |

Additionally, there are **fixed physical constants** (not tunable):

| Constant | Value | Description |
|----------|-------|-------------|
| `BYTE_COPY_COST_US` | 0.001 µs/byte | Byte-copy on TC3xx (~1 ns/byte) |
| `NVM_WRITE_COST_US` | 0.3 µs | NVM write per buffer entry |
| `TEST_FRF_DATA_COST_US` | 0.5 µs | TestFrfData fixed cost |
| `WAIT_CLR_RESP_COST_US` | 0.3 µs | WaitClrResp fixed cost |

---

## 4. Project Configuration (`ProjectConfig`)

All DEM parameters are extracted dynamically from `icsp_dem_cnf.c` and PTU headers by the `extractor` module. Key fields:

| Field | Source | Description |
|-------|--------|-------------|
| `NrFmy` | `Icsp_Dem_Cnf_Fmy_ConstStruct` | Failure memory entries |
| `NrFifoBas` | Same struct | Basic FIFO size |
| `NrFifoIntm` | Same struct | Intermediate FIFO size |
| `NrFifoRsv` | Same struct | Reserved FIFO entries |
| `NrClcFmyEveAsyn` | PTU headers / calibration | Max async events per recurrence |
| `NrClcFmyPost` | PTU headers / calibration | Max deferred post-processing |
| `NrEve` | `Icsp_Dem_Smad_SmadNum[]` array size | Total event count |
| `NrFrfDataTot` | `Icsp_Dem_Cnf_Frf_ConstStruct` | Total FRF data entries |
| `NrBlockFrf` | Same struct | Number of FRF blocks |
| `NrFrfPre` | `Icsp_Dem_Cnf_FrfPre_ConstStruct` | Pre-stored FRF count |
| `NrLamp` | `Icsp_Dem_Cnf_Lamp_ConstStruct` | Max lamp debounce entries |
| `FrfBlocks[]` | `Icsp_Dem_Cnf_Frf_Block_ConstStruct` | Per-block config (4 blocks typical) |

Each `FrfBlockConfig` contains: `NrByteFrame`, `NrFrfIdxCalMax`, `NrIdxPerClass`, `NrFrfHold`, `NrFrfTot`, `LfOptions`.

---

## 5. Scenarios

Three worst-case scenarios model different event injection patterns, each with specific calibration flag settings:

### Scenario 1 — Full Injection + Displacement (2nd Recurrence)

- `lc_enable_first_nr_fmy_events = 1`
- `lc_enable_next_nr_fmy_events = 1`
- FMY starts **empty**
- First batch fills FMY; second batch displaces (higher priority)
- **Worst case for displacement cost**

### Scenario 2 — First Batch Only

- `lc_enable_first_nr_fmy_events = 1`
- `lc_enable_next_nr_fmy_events = 0`
- FMY starts **empty**
- Only new entries (no displacement)
- **Baseline for new-entry cost**

### Scenario 3 — Pre-Filled FMY + Displacement (Two-Phase)

- **Phase 1** (not measured): fill FMY
- **Phase 2** (measured): inject events that displace
- FMY starts **full** (`fmy_initially_full = True`)
- FRF slots full → frame shifting required
- **Worst case for StoreFrf full-shift cost**

### Calibrations

For each scenario, the simulation is run across **6 standard calibration pairs** `(NrClcFmyEveAsyn, NrClcFmyPost)`:

```python
DEFAULT_CALIBRATIONS = (
    (5,  3),
    (5, 4),
    (5, 5),
    (10, 5),
    (10, 10),
    (20, 10),
)
```

This produces a **3 × 6 WCS grid** — the primary output of the simulation.

---

## 6. Simulation Engine (`DemMainFunctionSimulator`)

The `run(scenario)` method computes total runtime by summing costs:

$$T_{total} = T_{fixed} + T_{B1} + T_{L1a} + T_{L1b} + T_{Lamp} + T_{deferred} + T_{FrfPre} + T_{misc}$$

Where each term depends on the scenario parameters and project configuration. For example:

$$T_{L1a} = N_{new} \cdot c_{l1a\_new} + N_{displace} \cdot c_{l1a\_displace}$$

$$T_{StoreFrf} = \sum_{b=1}^{N_{blocks}} \begin{cases} c_{free} & \text{if free frames available} \\ c_{shift} + N_{shift\_bytes} \cdot c_{byte\_copy} & \text{if full} \end{cases}$$

---

## 7. Auto-Fit (Coordinate Descent)

When bench measurement data is available, `auto_fit()` minimizes the RMSE between simulated and measured values:

$$RMSE = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (T_{sim,i} - T_{bench,i})^2}$$

**Algorithm:**
1. Start from initial `MicroCosts` (e.g., `COSTS_PROJ2`).
2. For each iteration (max `FIT_MAX_ITERATIONS = 120`):
   - For each tunable field in `MicroCosts`:
     - Try perturbations: ±2%, ±5%, ±10%, ±15%, ±20%
     - Keep the perturbation that produces the lowest RMSE
3. Stop when improvement per iteration < `FIT_CONVERGENCE_THRESHOLD = 0.01` µs.

---

## 8. Monte Carlo Analysis

Simulates peak runtime under stochastic interrupt (IRQ) noise:

$$T_{sample} = T_{deterministic} + \epsilon, \quad \epsilon \sim \mathcal{N}(\mu_{IRQ}, \sigma_{IRQ})$$

- Default: `MC_DEFAULT_CYCLES = 200,000` samples, seed = 42
- Output: peak, mean, median, stdev, P95, P99, P99.9, 95% CI
- Stored in `MonteCarloResult` dataclass

---

## 9. Transfer Learning

For untested projects, `transfer_fit.py` implements:

1. **Structural distance** — normalized metric comparing `NrFmy`, `NrBlockFrf`, `NrEve`, etc. between the new project and all reference projects.
2. **Reference selection** — the closest known project (e.g., PROJ2 or PROJ3) is chosen.
3. **Cost adaptation** — starting from the reference costs, `auto_fit` is run if bench data exists; otherwise, the reference costs are used directly with `t_main_fixed` absorbing unknown function overhead.
4. **Enrichment** — the bench store provides all previously tested project configs and costs, expanding the candidate pool beyond the two hardcoded references.

---

## 10. Sensitivity Analysis

Explores how WCS runtime varies with calibration parameters:

- `NrClcFmyPost` swept through: `(3, 4, 5, 7, 10, 15, 20)`
- `NrClcFmyEveAsyn` swept through: `(5, 10, 15, 20, 30, 40)`

---

## 11. Thresholds

| Threshold | Value | Color |
|-----------|-------|-------|
| Yellow | > 500 µs | Warning — approaching critical |
| Red | > 700 µs | Critical — exceeds budget |

These are used in Excel report conditional formatting and GUI indicators.
