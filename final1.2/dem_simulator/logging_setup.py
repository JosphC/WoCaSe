"""Logging configuration for the DEM simulator."""

from __future__ import annotations

import logging
import sys
from typing import Optional


_LOG_FMT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
_LOG_DATE_FMT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger("dem_simulator")


def setup_logging(
    *,
    verbose: bool = False,
    log_file: Optional[str] = None,
) -> None:
    """Configure the logging subsystem.

    Parameters
    ----------
    verbose : bool
        If True, set level to DEBUG; otherwise INFO.
    log_file : str, optional
        If given, also write log output to this file.
    """
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        try:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter(_LOG_FMT, datefmt=_LOG_DATE_FMT))
            handlers.append(fh)
        except OSError as exc:
            print(f"  WARNING: Cannot open log file {log_file!r}: {exc}",
                  file=sys.stderr)

    logging.basicConfig(level=level, format=_LOG_FMT, datefmt=_LOG_DATE_FMT,
                        handlers=handlers, force=True)
    logger.setLevel(level)
