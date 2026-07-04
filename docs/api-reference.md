# API Reference

## 1. `wcs_modules` — Instrumentation & Build API

### `wcs_modules.main`

#### `process_system_file(proj_name, td5_path, build_type, rule, **kwargs) → Optional[SimulationResults]`

Processes a System File project end-to-end: instrument → build → (optionally) simulate.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `proj_name` | `str` | — | Project name (e.g., `"PROJ2_0U0_OB6_024"`) |
| `td5_path` | `str` | — | Path to `td5.exe` |
| `build_type` | `str` | — | `"NORMAL"` or `"RELEASE"` |
| `rule` | `str` | — | Build rule (e.g., `"All"`) |
| `target_name` | `Optional[str]` | `None` | Auto-detected if not provided |
| `run_simulation` | `bool` | `False` | Enable post-build simulation |
| `sim_generate_excel` | `bool` | `True` | Generate Excel report |
| `sim_run_monte_carlo` | `bool` | `True` | Run Monte Carlo analysis |
| `sim_mc_cycles` | `int` | `50_000` | Number of MC cycles |
| `progress_callback` | `Callable` | `None` | Progress message callback |

**Returns:** `SimulationResults` if `run_simulation=True`, else `None`.

**Raises:** `RuntimeError` on path/target resolution failure.

---

#### `process_mks_release(release_name, td5_path, build_type, rule, **kwargs) → Optional[SimulationResults]`

Same signature and behavior as `process_system_file`, but imports via MKS instead of filesystem.

---

#### `apply_modifications(case_name, work_dir) → None`

Applies all instrumentation modifications to a project's source files. Called internally by both `process_*` functions.

---

### `wcs_modules.arxml_processor`

#### `process_arxml(arxml_path) → Tuple[Optional[int], Optional[int]]`

Extracts the `NrFmy` value from an ARXML file.

**Returns:** `(val, val * 2)` or `(None, None)` if extraction fails.

---

### `wcs_modules.gpt_detector`

#### `find_function_pair_in_headers(root_folder) → Optional[Tuple[str, str]]`

Searches `.h` files for GPT timing function variants.

**Returns:** `(convert_function_name, gettime_function_name)` — e.g., `("Gpt_ConvertTicksToMicrosec", "Gpt_GetSystemTime")` or the `Iopt_*` variants. Returns `None` if not found.

---

### `wcs_modules.td5_builder`

#### `importfs(td5_path, case_name, proj_name) → None`

Imports a filesystem project into TD5.

#### `importmks(td5_path, release_name) → None`

Imports an MKS release into TD5.

#### `buildprj(td5_path, proj_name, target_name, build_type, rule) → None`

Builds a project using TD5 CLI.

#### `find_target_name_recursively(work_dir) → Optional[str]`

Discovers the build target by parsing `.tdxml` files in the project tree.

---

### `wcs_modules.path_utils`

#### `create_case_path(case_name, base_dir="d:\\casdev\\td5") → Optional[str]`

Resolves a project name to its full directory path following the naming convention.

#### `find_first_work_subdir(case_name) → Optional[str]`

Locates the `work` subdirectory within a project.

#### `find_project_file(filename, root_dir) → Optional[str]`

Recursively searches for a specific file in the project tree.

#### `find_folder(root_dir, target_folder) → Optional[str]`

Recursively searches for a specific folder path.

---

### `wcs_modules.code_modifier`

#### `add_headers_to_main_c(main_abs_path) → None`

Inserts WCS-specific `#include` directives after the last include block.

#### `modify_main_c(main_abs_path, val, convert_func, gettime_func) → None`

Injects runtime measurement instrumentation code into `icsp_dem_main.c`.

---

### `wcs_modules.simulator_bridge`

#### `run_post_build_simulation(case_path, proj_name, **kwargs) → SimulationResults`

Entry point for post-build simulation. Locates generated files, extracts config, runs simulation, and optionally generates Excel report.

#### `SimulationResults` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `project_name` | `str` | Project identifier |
| `nr_fmy` | `int` | Extracted NrFmy |
| `nr_eve` | `int` | Extracted NrEve |
| `wcs_grid` | `Dict[str, List[float]]` | `{"S1": [...], "S2": [...], "S3": [...]}` |
| `rmse_total` | `float` | Overall RMSE vs. bench (0 if no reference) |
| `rmse_per_scenario` | `Dict[str, float]` | Per-scenario RMSE |
| `mc_peak_us` | `float` | Monte Carlo peak runtime |
| `mc_mean_us` | `float` | Monte Carlo mean runtime |
| `mc_p99_us` | `float` | Monte Carlo P99 runtime |
| `excel_path` | `str` | Path to generated Excel report |
| `has_reference` | `bool` | Whether bench data was available |
| `num_variants` | `int` | PTU variants found |
| `calibration_labels` | `List[str]` | Column labels for WCS grid |
| `success` | `bool` | Overall success flag |
| `error_message` | `str` | Error description if failed |
| `warnings` | `List[str]` | Collected warnings |

---

## 2. `dem_simulator` — Simulation Engine API

### `dem_simulator.extractor`

#### `load_project_from_c(cnf_c_path, ptu_dir, project_name) → ProjectDefinition`

Parses `icsp_dem_cnf.c` and PTU header files to construct a complete `ProjectDefinition`.

#### `extract_project_config(cnf_c_path) → ProjectConfig`

Extracts just the base configuration from `icsp_dem_cnf.c`.

#### `extract_ptu_variants(ptu_dir, base_config) → List[ProjectConfig]`

Extracts PTU variant configurations from `icsp_dem_cnf_ptu*.h` headers.

---

### `dem_simulator.engine`

#### `DemMainFunctionSimulator(cfg, costs)`

**Constructor parameters:**

| Name | Type | Description |
|------|------|-------------|
| `cfg` | `ProjectConfig` | DEM configuration |
| `costs` | `MicroCosts` | Micro-cost model |

#### `.run(scenario) → float`

Simulates one scenario execution and returns the total runtime in µs.

---

### `dem_simulator.simulation`

#### `simulate_wcs_grid(cfg, costs, calibrations=None) → Dict[str, List[float]]`

Runs all 3 scenarios × N calibrations. Returns `{"S1": [...], "S2": [...], "S3": [...]}`.

#### `compute_rmse(simulated, reference) → float`

Computes RMSE between simulated and reference grids.

#### `compute_per_scenario_rmse(simulated, reference) → Dict[str, float]`

Per-scenario RMSE breakdown.

#### `auto_fit(cfg, starting_costs, bench_reference) → FitResult`

Coordinate-descent optimizer. Returns a `FitResult` with:
- `costs` — optimized `MicroCosts`
- `rmse_before`, `rmse_after` — improvement metrics
- `iterations` — number of iterations performed

---

### `dem_simulator.analysis`

#### `simulate_peak_runtime(cfg, costs, num_cycles, seed) → MonteCarloResult`

Monte Carlo peak-runtime simulation. Returns statistics (peak, mean, P95, P99, CI).

#### `sensitivity_analysis(cfg, costs) → Dict`

Sweeps `NrClcFmyPost` and `NrClcFmyEveAsyn` through predefined ranges.

#### `cross_variant_comparison(variants, costs) → Dict`

Compares WCS across multiple PTU variants.

#### `load_config_from_json(path) → ProjectConfig`

Loads a `ProjectConfig` from a JSON file.

---

### `dem_simulator.transfer_fit`

#### `infer_costs_for_project(cfg) → MicroCosts`

Estimates costs for a new project using transfer learning (no bench data needed).

#### `transfer_fit(cfg, bench_data) → FitResult`

Full transfer-learning fit: selects closest reference, then runs `auto_fit`.

---

### `dem_simulator.bench_store`

#### `get_fitted_costs(project_name) → Optional[MicroCosts]`

Retrieves pre-fitted costs from the SQLite store.

#### `upload_bench_result(project_name, costs, config, rmse) → None`

Uploads fitted costs and configuration to the store.

#### `set_store_path(path) → None`

Overrides the default store location.

---

### `dem_simulator.costs`

#### `get_project_costs(project_name, cfg=None) → MicroCosts`

Resolves costs through a priority chain:
1. Bench store (highest priority)
2. Hardcoded `PROJECT_COSTS` (exact match)
3. Prefix/token match in `PROJECT_COSTS`
4. Transfer learning (if `cfg` provided)
5. Default `MicroCosts()` (fallback)

#### Pre-fitted Cost Sets

| Constant | Project | Status |
|----------|---------|--------|
| `COSTS_PROJ1` | PROJ1 | Fitted from bench data |
| `COSTS_PROJ2` | PROJ2 | Fitted from bench data |
| `COSTS_PROJ3` | PROJ3 | Fitted from bench data |

---

### `dem_simulator.excel_report`

#### `generate_excel_report(project_def, costs, output_path, **kwargs) → str`

Generates a multi-sheet Excel report with:
- WCS grid table with conditional formatting (yellow > 500 µs, red > 700 µs)
- Bar charts per scenario
- Monte Carlo statistics
- Sensitivity analysis results
- Cross-variant comparison

Returns the path to the generated file.

---

### `dem_simulator.selftest`

#### `run_self_tests() → bool`

Validates simulation invariants:

1. **Monotonicity** — increasing `NrClcFmyEveAsyn` must not decrease WCS time
2. **Determinism** — same inputs produce identical outputs
3. **Non-negativity** — all simulated costs ≥ 0
4. **Bounds** — values within reasonable limits
5. **RMSE regression** — fitted costs achieve RMSE < 20 µs
6. **Config validation** — bad inputs raise `ConfigValidationError`

Returns `True` if all tests pass.
