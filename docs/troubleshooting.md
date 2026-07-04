# Troubleshooting

## Common Errors and Solutions

### Path & Project Resolution

| Error                                                | Cause                                                                                   | Solution                                                                                        |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `RuntimeError: Failed to create valid project path!` | Project name doesn't match the expected format (`XXYZZ_0U0_NNN` or `XXYZZ_0U0_NNN_MMM`) | Verify the name has a 5-character prefix (e.g., `PROJ2`) followed by underscore-separated parts |
| `RuntimeError: Project path does not exist`          | The resolved directory doesn't exist on disk                                            | Ensure the project has been extracted/imported to `d:\casdev\td5\...`                           |
| `RuntimeError: Work directory not found!`            | No `work` subdirectory found in the project tree                                        | Check that TD5 has extracted the project contents; look for a `work/` folder                    |

### Instrumentation

| Error                                            | Cause                                                                                             | Solution                                                                                               |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `Required GPT functions could not be determined` | Neither `Gpt_ConvertTicksToMicrosec` nor `Iopt_Gpt_ConvertTicksToMicrosec` found in any `.h` file | The tool falls back to manual user input; verify the correct variant is present in the project headers |
| `No file named 'project_options.tdcl' was found` | TDCL file not in expected location                                                                | Check that the project contains one of: `project_options.tdcl`, `errm.tdcl`, or `errm_agf.tdcl`        |
| `Folder 'errm_fctdg_test\i' was not found`       | Expected target folder doesn't exist in the project                                               | Verify the project structure; this folder is required for generated config files                       |

### Build

| Error                           | Cause                                            | Solution                                                                                                                       |
| ------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `Target name not found!`        | No visible `TargetInformation` in `.tdxml` files | Specify the target name manually in the UI                                                                                     |
| TD5 build fails (exit code ≠ 0) | Various build errors                             | Check terminal output for TD5-specific error messages; common causes: missing dependencies, locked files, incorrect build type |

### Simulation

| Error                                                     | Cause                                                         | Solution                                                                               |
| --------------------------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `SimulatorError: ProjectConfig must not be None`          | Engine initialized with `None` config                         | Ensure `extractor.load_project_from_c()` returned a valid result                       |
| `ConfigValidationError: NrFrfHold cannot exceed NrFrfTot` | Extracted config has invalid FRF block parameters             | Verify `icsp_dem_cnf.c` contains valid `Icsp_Dem_Cnf_Frf_Block_ConstStruct` data       |
| `FitConvergenceError`                                     | Auto-fit didn't reach convergence within `FIT_MAX_ITERATIONS` | Increase iteration budget in `constants.py`, or use `transfer_fit` as a starting point |

### Excel Report

| Error                         | Cause                                                      | Solution                       |
| ----------------------------- | ---------------------------------------------------------- | ------------------------------ |
| `ExcelReportError`            | Output file is locked (open in Excel) or permission denied | Close the Excel file and retry |
| Report not generated (silent) | `openpyxl` not installed (`HAS_OPENPYXL = False`)          | `pip install openpyxl`         |

### Bench Store

| Error                                          | Cause                              | Solution                                                                  |
| ---------------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------- |
| `sqlite3.OperationalError: database is locked` | Another process holds a write lock | Wait and retry; check for zombie Python processes                         |
| Store not found                                | Default path doesn't exist         | Set path via `DEM_BENCH_STORE` env var or `Tools → Set Bench Store Path…` |

### GUI

| Issue                             | Cause                          | Solution                                                                          |
| --------------------------------- | ------------------------------ | --------------------------------------------------------------------------------- |
| `[ERROR] PyQt6 is not installed!` | Python environment lacks PyQt6 | `pip install PyQt6`; the launcher script (`run_wcs_qt.bat`) attempts auto-install |
| Window appears blank / no theme   | High-DPI scaling issue         | Ensure PyQt6 ≥ 6.4; the app sets `PassThrough` rounding policy automatically      |
| Sidebar doesn't appear            | Splitter collapsed             | `Ctrl+B` or `View → Project Navigator` to toggle                                  |
