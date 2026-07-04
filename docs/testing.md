# Testing

## 1. Test Organization

The project has **19 test files** across two test suites:

### `tests/` — wcs_modules tests (10 files)

| File | Module Under Test |
|------|-------------------|
| `test_arxml_processor.py` | `wcs_modules.arxml_processor` |
| `test_code_modifier.py` | `wcs_modules.code_modifier` |
| `test_file_generator.py` | `wcs_modules.file_generator` |
| `test_gpt_detector.py` | `wcs_modules.gpt_detector` |
| `test_logging_config.py` | `wcs_modules.logging_config` |
| `test_path_utils.py` | `wcs_modules.path_utils` |
| `test_td5_builder.py` | `wcs_modules.td5_builder` |
| `test_tdcl_modifier.py` | `wcs_modules.tdcl_modifier` |
| `test_templates.py` | `wcs_modules.templates` |
| `test_xml_modifier.py` | `wcs_modules.xml_modifier` |

### `dem_simulator/tests/` — simulator tests (9 files)

| File | Module Under Test |
|------|-------------------|
| `test_analysis.py` | `dem_simulator.analysis` |
| `test_bench_store.py` | `dem_simulator.bench_store` |
| `test_config.py` | `dem_simulator.config` |
| `test_constants.py` | `dem_simulator.constants` |
| `test_costs.py` | `dem_simulator.costs` |
| `test_engine.py` | `dem_simulator.engine` |
| `test_scenarios.py` | `dem_simulator.scenarios` |
| `test_simulation.py` | `dem_simulator.simulation` |
| `test_transfer_fit.py` | `dem_simulator.transfer_fit` |

---

## 2. Running Tests

### All Tests

```powershell
cd final1.2
python -m pytest tests/ dem_simulator/tests/ -v
```

### Specific Test File

```powershell
python -m pytest dem_simulator/tests/test_engine.py -v
```

### With Coverage Report

```powershell
pip install pytest-cov
python -m pytest tests/ dem_simulator/tests/ --cov=wcs_modules --cov=dem_simulator --cov-report=html
# Open htmlcov/index.html in browser
```

---

## 3. Built-in Self-Tests

The `dem_simulator.selftest` module provides runtime invariant validation independent of the test framework:

```powershell
python -m dem_simulator --selftest
```

### Invariants Checked

| # | Invariant | Description |
|---|-----------|-------------|
| 1 | **Monotonicity** | Increasing `NrClcFmyEveAsyn` must not decrease WCS time |
| 2 | **Determinism** | Identical inputs always produce identical outputs |
| 3 | **Non-negativity** | All simulated cost components ≥ 0 |
| 4 | **Bounds** | Simulated values within reasonable physical limits |
| 5 | **RMSE regression** | Fitted costs achieve RMSE < 20 µs for known projects |
| 6 | **Config validation** | Invalid inputs correctly raise `ConfigValidationError` |

Self-tests discover projects from the standard directory structure and validate each one.

---

## 4. Test Categories

### Unit Tests

Test individual functions in isolation with controlled inputs:
- ARXML parsing with mock XML content
- Path resolution with various naming patterns
- Cost model validation
- Config dataclass validation (frozen fields, bounds checking)
- Template generation correctness

### Integration Tests

Test module interactions:
- `simulator_bridge` → `extractor` → `engine` → `simulation` chain
- `bench_store` SQLite operations (read, write, migration)
- `transfer_fit` with reference project selection

### Invariant Tests (Self-Test)

Mathematical properties that must always hold regardless of input:
- Monotonicity of runtime with respect to event count
- Determinism across repeated runs with same seed
- Physical constraint adherence (non-negative times)

---

## 5. Testing Strategy Notes

- **No external dependencies required**: Tests for `dem_simulator` can run without TD5, bench data, or network access.
- **Self-contained fixtures**: Test files create their own mock data (temporary files, in-memory configs).
- **Validation dataclasses**: `FrfBlockConfig` and `ProjectConfig` have built-in `__post_init__` validation that raises `ConfigValidationError` for invalid states (e.g., `NrFrfHold > NrFrfTot`).

> *Assumption: No CI/CD pipeline configuration (e.g., GitHub Actions, GitLab CI) was found in the repository. Adding one is recommended for automated test execution on every commit.*
