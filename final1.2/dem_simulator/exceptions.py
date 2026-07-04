"""Custom exception classes for the DEM simulator."""

from __future__ import annotations


class SimulatorError(Exception):
    """Base exception for all simulator errors."""


class ConfigValidationError(SimulatorError):
    """Raised when a configuration value is out of bounds."""


class FitConvergenceError(SimulatorError):
    """Raised when the auto-fit procedure fails to converge."""


class ExcelReportError(SimulatorError):
    """Raised when Excel report generation fails."""
