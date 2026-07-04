"""
Unit tests for tdcl_modifier module.

Tests cover:
  - find_and_insert_errm_include:
      • insert into file with content and newlines
      • skip when include already present
      • insert into empty file
      • insert into file with no newlines
      • return None when no TDCL file found
"""

import os
import tempfile
import unittest

from wcs_modules.tdcl_modifier import find_and_insert_errm_include, _INCLUDE_LINE


class TestFindAndInsertErrmInclude(unittest.TestCase):
    """Tests for find_and_insert_errm_include()."""

    def _create_tdcl_tree(self, content: str) -> str:
        """Helper: create a temp dir with project_options.tdcl inside a sub-folder."""
        tmp = tempfile.mkdtemp()
        sub = os.path.join(tmp, "config")
        os.makedirs(sub)
        filepath = os.path.join(sub, "project_options.tdcl")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return tmp

    def _read_file(self, base_dir: str) -> str:
        """Helper: read back the project_options.tdcl content."""
        for root, _, files in os.walk(base_dir):
            for fn in files:
                if fn == "project_options.tdcl":
                    with open(os.path.join(root, fn), "r", encoding="utf-8") as f:
                        return f.read()
        return ""

    def test_insert_after_first_newline(self):
        """Include is inserted after the first newline."""
        base = self._create_tdcl_tree("line1\nline2\nline3\n")
        result = find_and_insert_errm_include(base)
        self.assertIsNotNone(result)
        content = self._read_file(base)
        lines = content.split("\n")
        self.assertEqual(lines[0], "line1")
        self.assertEqual(lines[1], _INCLUDE_LINE)
        self.assertEqual(lines[2], "line2")

    def test_already_present_no_modification(self):
        """Returns path without modifying file if include already exists."""
        original = f"line1\n{_INCLUDE_LINE}\nline2\n"
        base = self._create_tdcl_tree(original)
        result = find_and_insert_errm_include(base)
        self.assertIsNotNone(result)
        content = self._read_file(base)
        self.assertEqual(content, original)

    def test_empty_file(self):
        """Include is written as the only content in an empty file."""
        base = self._create_tdcl_tree("")
        result = find_and_insert_errm_include(base)
        self.assertIsNotNone(result)
        content = self._read_file(base)
        self.assertEqual(content, _INCLUDE_LINE + "\n")

    def test_no_newline_in_content(self):
        """Appends newline + include when file has no newlines."""
        base = self._create_tdcl_tree("single_line_no_newline")
        result = find_and_insert_errm_include(base)
        self.assertIsNotNone(result)
        content = self._read_file(base)
        self.assertIn(_INCLUDE_LINE, content)
        self.assertTrue(content.startswith("single_line_no_newline\n"))

    def test_no_tdcl_file_returns_none(self):
        """Returns None when no project_options.tdcl exists."""
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "empty_folder"))
            result = find_and_insert_errm_include(tmp)
            self.assertIsNone(result)

    def test_returns_absolute_path(self):
        """Returned path is an absolute path to the actual file."""
        base = self._create_tdcl_tree("header\nbody\n")
        result = find_and_insert_errm_include(base)
        self.assertTrue(os.path.isabs(result))
        self.assertTrue(os.path.isfile(result))

    def test_idempotent(self):
        """Calling twice does not duplicate the include."""
        base = self._create_tdcl_tree("line1\nline2\n")
        find_and_insert_errm_include(base)
        find_and_insert_errm_include(base)
        content = self._read_file(base)
        self.assertEqual(content.count(_INCLUDE_LINE), 1)


if __name__ == "__main__":
    unittest.main()
