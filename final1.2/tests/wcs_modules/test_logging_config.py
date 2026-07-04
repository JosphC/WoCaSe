"""
Unit tests for logging_config module.

Tests cover:
  - setup_logging: handler creation, log file creation
  - get_logger: correct hierarchy
  - _DynamicStream: delegation to sys.stdout
  - _BareFormatter: raw message formatting
"""

import logging
import os
import sys
import tempfile
import unittest

from wcs_modules.logging_config import (
    setup_logging,
    get_logger,
    _DynamicStream,
    _BareFormatter,
)


class TestDynamicStream(unittest.TestCase):
    """Tests for _DynamicStream."""

    def test_write_delegates_to_stdout(self):
        """Write goes to whatever sys.stdout is at call time."""
        captured = []

        class FakeStdout:
            def write(self, msg):
                captured.append(msg)
                return len(msg)
            def flush(self):
                pass

        stream = _DynamicStream()
        old = sys.stdout
        try:
            sys.stdout = FakeStdout()
            stream.write("hello")
            self.assertEqual(captured, ["hello"])
        finally:
            sys.stdout = old

    def test_flush_delegates_to_stdout(self):
        """Flush calls sys.stdout.flush()."""
        flushed = []

        class FakeStdout:
            def write(self, msg):
                return len(msg)
            def flush(self):
                flushed.append(True)

        stream = _DynamicStream()
        old = sys.stdout
        try:
            sys.stdout = FakeStdout()
            stream.flush()
            self.assertEqual(flushed, [True])
        finally:
            sys.stdout = old


class TestBareFormatter(unittest.TestCase):
    """Tests for _BareFormatter."""

    def test_formats_only_message(self):
        formatter = _BareFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg="raw message", args=(), exc_info=None
        )
        self.assertEqual(formatter.format(record), "raw message")

    def test_formats_with_args(self):
        formatter = _BareFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="",
            lineno=0, msg="value=%d", args=(42,), exc_info=None
        )
        self.assertEqual(formatter.format(record), "value=42")


class TestSetupLogging(unittest.TestCase):
    """Tests for setup_logging()."""

    def setUp(self):
        """Clear any existing handlers and create a temp directory."""
        for name in ("wcs", "wcs.td5"):
            lgr = logging.getLogger(name)
            for h in lgr.handlers[:]:
                h.close()
                lgr.removeHandler(h)
        self._tmp = tempfile.mkdtemp()

    def _close_all_handlers(self):
        """Close and remove all logging handlers so files are released."""
        for name in ("wcs", "wcs.td5"):
            lgr = logging.getLogger(name)
            for h in lgr.handlers[:]:
                h.close()
                lgr.removeHandler(h)

    def tearDown(self):
        """Close handlers first, then remove the temp directory."""
        self._close_all_handlers()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_creates_log_directory(self):
        log_dir = os.path.join(self._tmp, "test_logs")
        setup_logging(log_dir=log_dir)
        self.assertTrue(os.path.isdir(log_dir))

    def test_creates_log_file(self):
        log_dir = os.path.join(self._tmp, "test_logs")
        setup_logging(log_dir=log_dir)
        log_files = [f for f in os.listdir(log_dir) if f.endswith(".log")]
        self.assertEqual(len(log_files), 1)

    def test_root_logger_has_two_handlers(self):
        setup_logging(log_dir=os.path.join(self._tmp, "logs"))
        root = logging.getLogger("wcs")
        self.assertEqual(len(root.handlers), 2)

    def test_td5_logger_does_not_propagate(self):
        setup_logging(log_dir=os.path.join(self._tmp, "logs"))
        td5 = logging.getLogger("wcs.td5")
        self.assertFalse(td5.propagate)

    def test_td5_logger_has_two_handlers(self):
        setup_logging(log_dir=os.path.join(self._tmp, "logs"))
        td5 = logging.getLogger("wcs.td5")
        self.assertEqual(len(td5.handlers), 2)

    def test_idempotent_no_duplicate_handlers(self):
        """Calling setup_logging twice does not add duplicate handlers."""
        log_dir = os.path.join(self._tmp, "logs")
        setup_logging(log_dir=log_dir)
        setup_logging(log_dir=log_dir)
        root = logging.getLogger("wcs")
        self.assertEqual(len(root.handlers), 2)


class TestGetLogger(unittest.TestCase):
    """Tests for get_logger()."""

    def test_returns_child_of_wcs(self):
        lgr = get_logger("mymodule")
        self.assertEqual(lgr.name, "wcs.mymodule")

    def test_returns_logger_instance(self):
        lgr = get_logger("test")
        self.assertIsInstance(lgr, logging.Logger)

    def test_different_names_different_loggers(self):
        a = get_logger("module_a")
        b = get_logger("module_b")
        self.assertIsNot(a, b)


if __name__ == "__main__":
    unittest.main()
