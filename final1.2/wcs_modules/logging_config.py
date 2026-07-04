"""
Logging Configuration Module

Provides centralised logging setup for the WCS tool.

Two handlers are configured:
  - Console (StreamHandler): no timestamps, format ``[LEVEL] message``
  - Log file (FileHandler):  with timestamps, format
    ``[YYYY-MM-DD HH:MM:SS] LEVEL - module - message``

A special "td5" logger exists for TD5 CLI output that is already
prefixed by the external tool.  On the console this output is printed
verbatim (no extra prefix), while in the log file it still gets a
timestamp so the chronological context is preserved.
"""

import logging
import os
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Dynamic stream wrapper – always delegates to the *current* sys.stdout
# so that logging output follows any runtime redirection (e.g. the Qt
# OutputRedirector installed by the worker thread).
# ---------------------------------------------------------------------------
class _DynamicStream:
    """A stream proxy that always writes to the current ``sys.stdout``."""

    def write(self, msg: str) -> int:
        return sys.stdout.write(msg)

    def flush(self) -> None:
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Custom formatter that prints messages *without* any prefix (used by the
# TD5 console handler so that lines coming from the external tool appear
# exactly as the tool emits them).
# ---------------------------------------------------------------------------
class _BareFormatter(logging.Formatter):
    """Formatter that emits only the raw message text."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
_LOG_DIR = os.path.join(r"D:\casdev\td5", "WCS_logs")


def setup_logging(log_dir: str = _LOG_DIR) -> None:
    """Initialise the root and ``td5`` loggers with console and file handlers.

    Call this **once** at application start-up (e.g. in ``wcs_qt.py``).
    Creates *log_dir* if it does not exist and opens an initial session log
    file.  Use :func:`rotate_log_file` at the start of each build to switch
    to a project-specific file.

    Args:
        log_dir: Directory where log files are stored.  Created automatically
                 if it does not exist.
    """
    # ---- Root logger -------------------------------------------------------
    root = logging.getLogger("wcs")
    root.setLevel(logging.DEBUG)

    # Prevent duplicate handlers on repeated calls
    if root.handlers:
        return

    # Create log directory and initial log file
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(log_dir, f"WoCaSe_{timestamp}.log")

    file_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler – no timestamps, follows sys.stdout dynamically
    console_handler = logging.StreamHandler(_DynamicStream())
    console_handler.setLevel(logging.DEBUG)
    console_handler.terminator = ""  # QTextEdit.append() adds its own newline
    console_fmt = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_fmt)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_fmt)

    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # ---- TD5 logger (child of wcs) ----------------------------------------
    # TD5 CLI output is already decorated by the external tool, so the
    # console handler should print it *verbatim* (no [INFO] prefix).
    td5_logger = logging.getLogger("wcs.td5")
    td5_logger.propagate = False  # Do NOT send to root handlers

    td5_console = logging.StreamHandler(_DynamicStream())
    td5_console.setLevel(logging.DEBUG)
    td5_console.terminator = ""  # QTextEdit.append() adds its own newline
    td5_console.setFormatter(_BareFormatter())

    td5_file = logging.FileHandler(log_file, encoding="utf-8")
    td5_file.setLevel(logging.DEBUG)
    td5_file.setFormatter(file_fmt)

    td5_logger.addHandler(td5_console)
    td5_logger.addHandler(td5_file)


def rotate_log_file(project_name: str = "", log_dir: str = _LOG_DIR) -> str:
    """Switch all file handlers to a new log file for a new project run.

    Call this once at the start of each build / pipeline run so that each
    project gets its own dated log file instead of sharing the session file.

    The new file is named::

        wcs_<project_name>_<YYYY-MM-DD_HH-MM-SS>.log

    If *project_name* is empty the ``wcs_`` prefix is used alone.

    Console (StreamHandler) handlers are **not** touched — only
    FileHandler instances are replaced.

    Args:
        project_name: Human-readable project / release identifier that
                      becomes part of the file name.  Slashes and spaces
                      are replaced by underscores.
        log_dir: Directory for the new log file.  Defaults to the same
                 directory used by :func:`setup_logging`.

    Returns:
        Absolute path of the newly opened log file.
    """
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = project_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
    stem = f"wcs_{safe_name}_{timestamp}" if safe_name else f"wcs_{timestamp}"
    log_file = os.path.join(log_dir, f"{stem}.log")

    file_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    def _swap_file_handlers(lgr: logging.Logger) -> None:
        """Replace every FileHandler on *lgr* with one writing to *log_file*."""
        to_remove = [h for h in lgr.handlers if isinstance(h, logging.FileHandler)]
        for h in to_remove:
            h.flush()
            h.close()
            lgr.removeHandler(h)
        new_fh = logging.FileHandler(log_file, encoding="utf-8")
        new_fh.setLevel(logging.DEBUG)
        new_fh.setFormatter(file_fmt)
        lgr.addHandler(new_fh)

    _swap_file_handlers(logging.getLogger("wcs"))
    _swap_file_handlers(logging.getLogger("wcs.td5"))

    logging.getLogger("wcs").info(
        "[rotate_log_file] New log file opened for project '%s': %s",
        project_name, log_file,
    )
    return log_file


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``wcs`` hierarchy.

    Usage::

        from wcs_modules.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A :class:`logging.Logger` instance.
    """
    return logging.getLogger(f"wcs.{name}")
