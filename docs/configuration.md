# Configuration

## 1. Build System Constants

Defined in `wcs_modules/__init__.py`:

```python
TD5_PATH   = r"C:\LegacyApp\TD5\4.4.0\eclipse_cli\td5.exe"
BUILD_TYPE = "NORMAL"      # or "RELEASE"
BUILD_RULE = "All"
```

These serve as defaults in the GUI and can be overridden per-run through the Instrumentation tab.

---

## 2. Project Path Resolution

Defined in `wcs_modules/path_utils.py`:

| Parameter  | Default         | Description                         |
| ---------- | --------------- | ----------------------------------- |
| `base_dir` | `d:\casdev\td5` | Root directory for all TD5 projects |

Project names are resolved by convention:

| Input               | Resolved Path                                |
| ------------------- | -------------------------------------------- |
| `PROJ2_0U0_OB6_024` | `d:\casdev\td5\PR\OJ2\OB6\PROJ2_0U0_OB6_024` |
| `PROJ6_0U0_000`     | `d:\casdev\td5\PR\OJ6\000\PROJ6_0U0_000`     |

---

## 3. Bench Store

### Location

The SQLite database (`bench_store.db`) location is resolved in this order:

1. Value set via `bench_store.set_store_path(path)`
2. Environment variable `DEM_BENCH_STORE`
3. Default: next to the `dem_simulator` package

### Behavior

- Uses **WAL mode** for concurrent read access
- Atomic transactions (`BEGIN … COMMIT`)
- GUI path override: `Tools → Set Bench Store Path…`

### Bench Results Directory

Used by `BenchUploadDialog`:

| Parameter     | Value                                    |
| ------------- | ---------------------------------------- |
| Root          | `d:\casdev\td5\BM\bench_results`         |
| Expected file | `<project>/RuntimeMeasureReduction.xlsx` |

---

## 4. Simulation Constants

Defined in `dem_simulator/constants.py`:

### Auto-Fit Parameters

| Constant                    | Value                      | Purpose                                   |
| --------------------------- | -------------------------- | ----------------------------------------- |
| `FIT_MAX_ITERATIONS`        | 120                        | Maximum optimization iterations           |
| `FIT_CONVERGENCE_THRESHOLD` | 0.01 µs                    | Minimum RMSE improvement per iteration    |
| `FIT_DELTA_FRACTIONS`       | ±2%, ±5%, ±10%, ±15%, ±20% | Perturbation steps for coordinate descent |

### Default Calibrations

Six standard `(NrClcFmyEveAsyn, NrClcFmyPost)` pairs:

```python
DEFAULT_CALIBRATIONS = (
    (5,  3),
    (10, 5),
    (15, 7),
    (20, 10),
    (30, 15),
    (40, 20),
)
```

---

## 5. Logging Configuration

### `wcs_modules` Logging (`logging_config.py`)

| Handler                   | Format                                           | Destination                  |
| ------------------------- | ------------------------------------------------ | ---------------------------- |
| Console (`StreamHandler`) | `[LEVEL] message`                                | `sys.stdout` (dynamic proxy) |
| File (`FileHandler`)      | `[YYYY-MM-DD HH:MM:SS] LEVEL - module - message` | `wcs_modules/logs/`          |

- Uses a `_DynamicStream` proxy to follow runtime `stdout` redirection (e.g., Qt worker thread)
- TD5 sub-logger (`wcs.td5`) uses a bare formatter (no prefix) for console output
- Log rotation on application start via `rotate_log_file()`

### `dem_simulator` Logging (`logging_setup.py`)

Standard Python logging under the `dem_simulator` logger name.
