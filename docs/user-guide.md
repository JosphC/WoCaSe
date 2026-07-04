# User Guide

## 1. Starting the Application

### GUI Mode

```powershell
cd final1.2
python wcs_qt.py
```

Or use the Windows launcher:

```powershell
.\run_wcs_qt.bat
```

The launcher automatically checks for PyQt6 and installs it if missing.

### CLI Mode (Simulator Only)

```powershell
python -m dem_simulator              # Interactive project selection
python -m dem_simulator PROJ2        # Single project
python -m dem_simulator ALL          # All discovered projects
python -m dem_simulator --fit        # Auto-fit costs, then simulate
python -m dem_simulator --selftest   # Run invariant validation
```

---

## 2. GUI Layout

The main window (`ModernWCSApp`) consists of:

```
┌─────────────────────────────────────────────────────────┐
│  ☰  File   Edit   Tools   View   Help       [status]   │  ← Menu Bar
├──────────┬──────────────────────────────────────────────┤
│ EXPLORER │  [ Instrumentation ]  [ Train Simulator ]    │  ← Pill Tabs
│          │                                              │
│ 📂 PROJ2 │  ┌──────────────────────────────────────┐   │
│ 📂 PROJ3 │  │                                      │   │
│          │  │       Tab Content Area               │   │
│          │  │                                      │   │
│          │  └──────────────────────────────────────┘   │
│          │                                              │
│          │  [████████████████████]  Progress Bar         │
│          │  [     Run Instrumentation     ]  [00:00]    │
│          ├──────────────────────────────────────────────┤
│          │  Terminal Output Panel (resizable)            │
│          │  > [CMD] Processing: PROJ2_0U0_OB6_024       │
│          │  > Building target _FS_PROJ2_0U0_NORMAL...   │
├──────────┴──────────────────────────────────────────────┤
│  Ready                          Schaeffler | WoCaSe v1  │  ← Status Bar
└─────────────────────────────────────────────────────────┘
```

### 2.1 Project Navigator (Sidebar)

- **Toggle:** Hamburger button (☰) or `Ctrl+B` or `View → Project Navigator`
- **Import project:** `File → Import Project…` (`Ctrl+I`) — opens a folder picker
- **Load project:** Double-click a project entry to populate the Instrumentation form
- **Remove / Clear:** Footer buttons to remove individual or all entries
- **Persistence:** History is saved in Windows Registry (`QSettings`) and restored on launch
- **Context menu:** Right-click for additional options

### 2.2 Terminal Panel

- Displays all `stdout`/`stderr` output from the background worker
- TD5 CLI output appears verbatim (no extra prefix)
- Clear with `File → Clear Terminal` (`Ctrl+L`)
- Resizable via the horizontal splitter handle between tabs and terminal

---

## 3. Tab: Instrumentation

This tab drives the complete pipeline: **Instrument → Build → (optionally) Simulate → Report**.

### Input Fields

| Field | Description | Example |
|-------|-------------|---------|
| **Source Type** | Radio buttons: `System File` or `MKS Release` | — |
| **Project / Release Name** | The project identifier following the naming convention | `PROJ2_0U0_OB6_024` |
| **TD5 Path** | Path to `td5.exe` (pre-filled from `wcs_modules/__init__.py`) | `C:\LegacyApp\TD5\4.4.0\eclipse_cli\td5.exe` |
| **Build Type** | Dropdown: `NORMAL` or `RELEASE` | `NORMAL` |
| **Build Rule** | Build rule passed to TD5 | `All` |
| **Target Name** | *(Optional)* — auto-detected from `.tdxml` if left empty | `_FS_PROJ2_0U0_NORMAL` |

### Simulation Options

| Checkbox | Default | Description |
|----------|---------|-------------|
| **Run simulation after build** | Off | Enables Extract + Simulate + Report stages |
| **Generate Excel report** | On | Produces the Excel file with charts and tables |
| **Run Monte Carlo** | On | Adds Monte Carlo peak-runtime analysis |
| **MC Cycles** | 50,000 | Number of Monte Carlo simulation cycles |

### Running

1. Fill in the project name and verify/adjust the build settings.
2. *(Optional)* Enable simulation options.
3. Click **"Run Instrumentation"**.
4. Monitor progress in the terminal panel and progress bar.
5. An elapsed-time counter appears during execution.
6. On completion, a success/error dialog is shown.

If simulation was enabled, a **Results** tab appears automatically with the WCS grid, RMSE values, Monte Carlo statistics, and a link to the generated Excel report.

---

## 4. Tab: Train Simulator

Used to calibrate the simulation model against real bench measurements.

### Workflow

1. Navigate to `Tools → Train Simulator from Bench…` or select the **Train Simulator** tab.
2. Enter the project folder name (e.g., `PROJ2_0U0_OB6_024`).
3. The dialog shows validation indicators:
   - ✓/✗ for the project directory under `d:\casdev\td5\PR\bench_results\<project>`
   - ✓/✗ for `RuntimeMeasureReduction.xlsx` within that directory
4. Click **"Import & Train"**.
5. The tool:
   - Reads bench measurement data from the Excel file
   - Extracts DEM configuration from `icsp_dem_cnf.c` in the project tree
   - Runs `auto_fit` (coordinate-descent) to minimize RMSE
   - Uploads fitted costs to `bench_store.db`

---

## 5. Menu Reference

### File

| Action | Shortcut | Description |
|--------|----------|-------------|
| Import Project… | `Ctrl+I` | Add a project folder to the navigator |
| Clear Terminal | `Ctrl+L` | Clear all terminal output |
| Exit | `Ctrl+Q` | Close the application |

### Edit

| Action | Shortcut |
|--------|----------|
| Undo | `Ctrl+Z` |
| Redo | `Ctrl+Y` |
| Cut / Copy / Paste | `Ctrl+X` / `Ctrl+C` / `Ctrl+V` |
| Delete | `Del` |
| Select All | `Ctrl+A` |
| Find / Replace… | `Ctrl+H` |

### Tools

| Action | Description |
|--------|-------------|
| Train Simulator from Bench… | Opens the bench import + training dialog |
| Set Bench Store Path… | Change the SQLite store location |

### View

| Action | Shortcut | Description |
|--------|----------|-------------|
| Project Navigator | `Ctrl+B` | Toggle sidebar visibility |
| Enable DEM Simulation | `Ctrl+D` | Toggle simulation after build |

### Help

| Action | Shortcut | Description |
|--------|----------|-------------|
| Contact Support | `Ctrl+Shift+S` | Opens Teams/Outlook contact dialog |
| About WoCaSe | — | Version and author information |

---

## 6. Keyboard Shortcuts Summary

| Shortcut | Action |
|----------|--------|
| `Ctrl+I` | Import Project |
| `Ctrl+L` | Clear Terminal |
| `Ctrl+Q` | Exit |
| `Ctrl+B` | Toggle Project Navigator |
| `Ctrl+D` | Toggle DEM Simulation |
| `Ctrl+H` | Find / Replace |
| `Ctrl+Shift+S` | Contact Support |

---

## 7. Naming Conventions

WoCaSe resolves project paths based on a strict naming convention:

```
PROJ2_0U0_OB6_024
│││││ │││ │││ │││
└┬┘└┬┘ │   │   └── Release number
 │  │   │   └────── OB code
 │  │   └────────── Separator
 │  └────────────── Platform
 └───────────────── Brand

Resolved path: d:\casdev\td5\PR\OJ2\OB6\PROJ2_0U0_OB6_024
```

For shorter names (e.g., `PROJ6_0U0_000`):

```
Resolved path: d:\casdev\td5\PR\OJ6\000\PROJ6_0U0_000
```

---

## 8. Output Files

### Generated by Instrumentation

| File | Location | Purpose |
|------|----------|---------|
| `errm_wcs.dcnfxml` | `errm_fctdg_test\i` | Diagnostics configuration XML |
| `errm_wcs.grl` | `errm_fctdg_test\i` | GRL rule file |
| `errm_wcs_test.cbd` | `errm_fctdg_test\i` | CBD configuration block |
| `icsp_dem_test_genr.xml` | project-specific | Test generation XML |

### Generated by Simulation

| File | Content |
|------|---------|
| Excel report (`.xlsx`) | WCS grid, RMSE, Monte Carlo stats, sensitivity charts |

### Logs

All operations are logged to `wcs_modules/logs/` with daily rotation.
