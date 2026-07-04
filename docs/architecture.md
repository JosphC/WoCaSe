# Architecture

## System Overview

WoCaSe is composed of two loosely coupled subsystems that communicate through a bridge module:

![WoCaSe Architecture](/docs/images/architecture.png)

## Subsystem A: `wcs_modules` — Instrumentation & Build

### Purpose

Automates the manual process of instrumenting an AUTOSAR DEM project for worst-case runtime measurement, then building it via the TD5 toolchain.

### Module Dependency Graph

```
qt_ui.py (GUI)
  └──► main.py (Orchestrator)
         ├──► path_utils.py         — Resolve project paths
         ├──► gpt_detector.py       — Detect GPT function variants in headers
         ├──► arxml_processor.py    — Extract NrFmy from ARXML
         ├──► file_generator.py     — Create errm_wcs.{dcnfxml,grl,cbd}
         │      └──► templates.py   — Text templates for generated files
         ├──► tdcl_modifier.py      — Insert #include in .tdcl files
         ├──► code_modifier.py      — Instrument icsp_dem_main.c
         │      └──► templates.py
         ├──► xml_modifier.py       — Modify CBD/XML files
         │      └──► templates.py
         ├──► td5_builder.py        — CLI calls to td5.exe
         └──► simulator_bridge.py   — Post-build simulation entry point
                └──► dem_simulator.*
```

### Key Classes

| Class                  | Module           | Description                                              |
| ---------------------- | ---------------- | -------------------------------------------------------- |
| `ModernWCSApp`         | `qt_ui.py`       | Main window (`QMainWindow`); 2 tabs + terminal + sidebar |
| `_Worker`              | `qt_ui.py`       | Background thread (`QThread`) executing the pipeline     |
| `BenchUploadDialog`    | `qt_ui.py`       | Dialog for importing bench measurement data              |
| `ContactSupportDialog` | `qt_ui.py`       | Contact information dialog                               |
| `TargetEntry`          | `td5_builder.py` | Lightweight container for parsed build targets           |

### Data Flow: Full Pipeline

```
User Input (project name, build settings)
    │
    ▼
path_utils.create_case_path()        → resolve d:\casdev\td5\XX\YZZ\...
    │
    ▼
gpt_detector.find_function_pair()    → identify Gpt_* or Iopt_Gpt_* API
    │
    ▼
arxml_processor.process_arxml()      → extract NrFmy integer
    │
    ▼
file_generator.create_*()           → write errm_wcs.dcnfxml / .grl / .cbd
    │
    ▼
tdcl_modifier.find_and_insert()     → patch project_options.tdcl
    │
    ▼
code_modifier.modify_main_c()       → inject timing instrumentation
    │
    ▼
xml_modifier.modify_icsp_dem_cbd()  → update CBD/XML references
    │
    ▼
td5_builder.importfs() + buildprj() → compile via TD5 CLI
    │
    ▼ (if simulation enabled)
simulator_bridge.run_post_build_simulation()
    ├── extractor.load_project_from_c()
    ├── simulation.simulate_wcs_grid()
    ├── analysis.simulate_peak_runtime()
    └── excel_report.generate_excel_report()
    │
    ▼
SimulationResults → emitted to UI via pyqtSignal
```

---

## Subsystem B: `dem_simulator` — Analytical Simulation Engine

### Purpose

Predicts the value of `debug_dem_highest_time` (the peak runtime of `Icsp_Dem_MainFunction()`) without requiring physical ECU measurements, using an analytical micro-cost model.

### Module Dependency Graph

```
__main__.py (CLI)
  └──► extractor.py         — Parse icsp_dem_cnf.c + PTU headers
         └──► config.py     — ProjectConfig, FrfBlockConfig
  └──► costs.py             — MicroCosts dataclass + fitted sets
  └──► scenarios.py         — 3 WCS scenarios × 6 calibrations
  └──► engine.py            — DemMainFunctionSimulator (core)
         ├──► config.py
         ├──► costs.py
         └──► scenarios.py
  └──► simulation.py        — WCS grid, RMSE, auto-fit
  └──► analysis.py          — Monte Carlo, sensitivity, cross-variant
  └──► transfer_fit.py      — Transfer learning for new projects
  └──► bench_store.py       — Collaborative SQLite store API
         └──► bench_store_db.py  — Low-level SQLite (WAL, transactions)
  └──► excel_report.py      — Excel report with charts
  └──► selftest.py          — Invariant validation
  └──► exceptions.py        — Custom exception hierarchy
```

### Key Classes

| Class                      | Module                | Description                                             |
| -------------------------- | --------------------- | ------------------------------------------------------- |
| `ProjectConfig`            | `config.py`           | All DEM parameters affecting MainFunction runtime       |
| `FrfBlockConfig`           | `config.py`           | Per-block freeze-frame configuration (frozen dataclass) |
| `ProjectDefinition`        | `config.py`           | Groups config + metadata for a full project definition  |
| `MicroCosts`               | `costs.py`            | Per-operation costs in µs (20 tunable fields)           |
| `Scenario`                 | `scenarios.py`        | Frozen dataclass modeling one WCS scenario              |
| `DemMainFunctionSimulator` | `engine.py`           | Step-by-step execution model                            |
| `MonteCarloResult`         | `analysis.py`         | Result container for MC analysis                        |
| `FitResult`                | `simulation.py`       | Result container for auto-fit optimization              |
| `SimulationResults`        | `simulator_bridge.py` | Container returned to the GUI                           |

### Exception Hierarchy

```
SimulatorError (base)
  ├── ConfigValidationError    — Invalid config parameter
  ├── FitConvergenceError      — Auto-fit failed to converge
  └── ExcelReportError         — Report generation failure
```

---

## Cross-Cutting Concerns

### Logging

Two independent logging configurations:

| Logger          | Module                           | Console Format    | File Format                                      |
| --------------- | -------------------------------- | ----------------- | ------------------------------------------------ |
| `wcs.*`         | `wcs_modules/logging_config.py`  | `[LEVEL] message` | `[YYYY-MM-DD HH:MM:SS] LEVEL - module - message` |
| `dem_simulator` | `dem_simulator/logging_setup.py` | Standard          | Standard with timestamps                         |

The `wcs.td5` sub-logger uses a bare formatter (no prefix) for console output so that TD5 CLI output appears unmodified.

### Threading Model (GUI)

- **Main thread:** Qt event loop, UI rendering
- **Worker thread (`_Worker`):** Executes the full pipeline; communicates via 4 `pyqtSignal`s:
  - `progress(str)` — Status messages
  - `command_output(str)` — Terminal output lines
  - `finished(bool, str)` — Success flag + message
  - `simulation_done(object)` — `SimulationResults` container

`stdout`/`stderr` are redirected to the terminal widget via the `_Redirect` wrapper during worker execution.

### Persistence

| Data                  | Storage                        | Location                          |
| --------------------- | ------------------------------ | --------------------------------- |
| Bench costs + configs | SQLite (WAL)                   | `bench_store.db`                  |
| Project history       | `QSettings` (Windows Registry) | `HKCU\Software\Schaeffler\WoCaSe` |
| Log files             | Rotating text files            | `wcs_modules/logs/`               |
