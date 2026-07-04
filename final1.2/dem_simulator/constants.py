"""Constants and enumerations used throughout the DEM simulator."""

from __future__ import annotations

import enum
from typing import Tuple


# ==============================================================================
# Elementary cost constants
# ==============================================================================

# Byte-copy cost in us per byte (approx 5 ns/byte on TC3xx LMU/SRAM non-cached;
# original 1 ns/byte was too optimistic — real worst-case adds pipeline stalls)
BYTE_COPY_COST_US: float = 0.005

# NVM write cost per buffer entry (us)
NVM_WRITE_COST_US: float = 0.3

# TestFrfData fixed cost (us)
TEST_FRF_DATA_COST_US: float = 0.5

# WaitClrResp fixed cost (us)
WAIT_CLR_RESP_COST_US: float = 0.3

# Default ISR jitter addend (us) — overridden per project in MicroCosts
# Derived from Tabelle2: "with interrupts" − "without interrupts" at Cal1 ≈ 110 µs
ISR_JITTER_DEFAULT_US: float = 0.0

# Default cold-cache penalty per FRF block (us) — first-touch on PFLASH/PSPR
CACHE_MISS_PER_BLOCK_DEFAULT_US: float = 0.0

# ==============================================================================
# Monte Carlo defaults
# ==============================================================================

MC_DEFAULT_CYCLES: int = 200_000
MC_DEFAULT_SEED: int = 42
MC_IRQ_MU: float = 0.5
MC_IRQ_SIGMA: float = 1.0

# ==============================================================================
# Auto-fit defaults
# ==============================================================================

FIT_MAX_ITERATIONS: int = 120
FIT_CONVERGENCE_THRESHOLD: float = 0.01
"""Stop when RMSE improvement per iteration is less than this (us)."""

FIT_DELTA_FRACTIONS: Tuple[float, ...] = (0.20, 0.15, 0.10, 0.05, 0.02,
                                           -0.02, -0.05, -0.10, -0.15, -0.20)

# ==============================================================================
# Sensitivity sweep ranges
# ==============================================================================

SENSITIVITY_POST_VALS: Tuple[int, ...] = (3, 4, 5, 7, 10, 15, 20)
SENSITIVITY_EA_VALS: Tuple[int, ...] = (5, 10, 15, 20, 30, 40)


# ==============================================================================
# Scenario type enumeration
# ==============================================================================

class ScenarioType(enum.Enum):
    """Typed enumeration of WCS scenario keys."""
    SCENARIO_1 = "scenario_1"
    SCENARIO_2 = "scenario_2"
    SCENARIO_3 = "scenario_3"
