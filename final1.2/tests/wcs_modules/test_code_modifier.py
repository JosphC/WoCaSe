"""
Unit tests for code_modifier module.

Tests cover:
  - is_comment: various comment and non-comment lines
  - lines_block_exists: block present, absent, edge cases
  - insert_headers_after_last_include: header insertion with real files
  - insert_code_in_function: code injection into C functions
"""

import os
import tempfile
import unittest

from wcs_modules.code_modifier import (
    is_comment,
    lines_block_exists,
    insert_headers_after_last_include,
    insert_code_in_function,
)


class TestIsComment(unittest.TestCase):
    """Tests for is_comment()."""

    def test_line_comment(self):
        self.assertTrue(is_comment("// this is a comment"))

    def test_block_comment_start(self):
        self.assertTrue(is_comment("/* block comment"))

    def test_block_comment_continuation(self):
        self.assertTrue(is_comment(" * continuation"))

    def test_block_comment_end(self):
        self.assertTrue(is_comment("  end of block */"))

    def test_empty_string(self):
        self.assertTrue(is_comment(""))

    def test_whitespace_only(self):
        self.assertTrue(is_comment("   \t  "))

    def test_code_line(self):
        self.assertFalse(is_comment("int x = 5;"))

    def test_include_line(self):
        self.assertFalse(is_comment('#include "file.h"'))

    def test_indented_comment(self):
        self.assertTrue(is_comment("    // indented comment"))


class TestLinesBlockExists(unittest.TestCase):
    """Tests for lines_block_exists()."""

    def test_block_present(self):
        """Block is found within the function range."""
        lines = [
            "void func(void)\n",    # 0 = func_start
            "{\n",                    # 1
            "    uint32 tmp_time;\n", # 2
            "    uint32 tmp_time_old;\n",
            "    uint32 tmp_time_new;\n",
            "    code();\n",
            "}\n",                    # 6 = func_end
        ]
        block = ["uint32 tmp_time;", "uint32 tmp_time_old;", "uint32 tmp_time_new;"]
        self.assertTrue(lines_block_exists(lines, 1, 6, block))

    def test_block_absent(self):
        """Block is not in the function."""
        lines = [
            "void func(void)\n",
            "{\n",
            "    int a = 1;\n",
            "    int b = 2;\n",
            "}\n",
        ]
        block = ["uint32 tmp_time;", "uint32 tmp_time_old;", "uint32 tmp_time_new;"]
        self.assertFalse(lines_block_exists(lines, 1, 4, block))

    def test_partial_match_is_not_accepted(self):
        """Only the first two of three lines match -> False."""
        lines = [
            "{\n",
            "    uint32 tmp_time;\n",
            "    uint32 tmp_time_old;\n",
            "    int different;\n",
            "}\n",
        ]
        block = ["uint32 tmp_time;", "uint32 tmp_time_old;", "uint32 tmp_time_new;"]
        self.assertFalse(lines_block_exists(lines, 0, 4, block))


class TestInsertHeadersAfterLastInclude(unittest.TestCase):
    """Tests for insert_headers_after_last_include()."""

    def test_inserts_after_last_include(self):
        """New header appears after the last existing #include."""
        content = (
            '#include "a.h"\n'
            '#include "b.h"\n'
            '\n'
            'void main(void) {}\n'
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c",
                                         delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            insert_headers_after_last_include(path, ['#include "new.h"'])
            with open(path, "r", encoding="utf-8") as f:
                result = f.read()
            lines = result.splitlines()
            self.assertEqual(lines[0], '#include "a.h"')
            self.assertEqual(lines[1], '#include "b.h"')
            self.assertEqual(lines[2], '#include "new.h"')
        finally:
            os.unlink(path)

    def test_does_not_duplicate_existing_header(self):
        """Skips insertion when header already exists."""
        content = (
            '#include "a.h"\n'
            '#include "new.h"\n'
            '\n'
            'void main(void) {}\n'
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c",
                                         delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            insert_headers_after_last_include(path, ['#include "new.h"'])
            with open(path, "r", encoding="utf-8") as f:
                result = f.read()
            self.assertEqual(result.count('#include "new.h"'), 1)
        finally:
            os.unlink(path)


class TestInsertCodeInFunction(unittest.TestCase):
    """Tests for insert_code_in_function()."""

    _C_SOURCE = (
        '#include "header.h"\n'
        '\n'
        'void Icsp_Dem_MainFunction(void)\n'
        '{\n'
        '    existing_code();\n'
        '}\n'
    )

    def test_inserts_start_and_end_code(self):
        """Start code is inserted after '{', end code before '}'."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c",
                                         delete=False, encoding="utf-8") as f:
            f.write(self._C_SOURCE)
            path = f.name
        try:
            start_code = "    uint32 tmp_time;\n    uint32 tmp_time_old;\n    uint32 tmp_time_new;\n"
            end_code = "    tmp_time_new = Convert(GetTime());\n"
            insert_code_in_function(
                path, "Icsp_Dem_MainFunction",
                start_code, end_code,
                "Convert", "GetTime"
            )
            with open(path, "r", encoding="utf-8") as f:
                result = f.read()
            self.assertIn("uint32 tmp_time;", result)
            self.assertIn("tmp_time_new = Convert(GetTime());", result)
        finally:
            os.unlink(path)

    def test_does_not_duplicate(self):
        """Second call does not re-insert code."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c",
                                         delete=False, encoding="utf-8") as f:
            f.write(self._C_SOURCE)
            path = f.name
        try:
            start_code = "    uint32 tmp_time;\n    uint32 tmp_time_old;\n    uint32 tmp_time_new;\n"
            end_code = "    tmp_time_new = Convert(GetTime());\n"
            insert_code_in_function(
                path, "Icsp_Dem_MainFunction",
                start_code, end_code,
                "Convert", "GetTime"
            )
            insert_code_in_function(
                path, "Icsp_Dem_MainFunction",
                start_code, end_code,
                "Convert", "GetTime"
            )
            with open(path, "r", encoding="utf-8") as f:
                result = f.read()
            self.assertEqual(result.count("uint32 tmp_time;"), 1)
        finally:
            os.unlink(path)

    def test_missing_function_does_nothing(self):
        """No changes when function name is not found."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c",
                                         delete=False, encoding="utf-8") as f:
            f.write(self._C_SOURCE)
            path = f.name
        try:
            original = self._C_SOURCE
            insert_code_in_function(
                path, "NonExistentFunction",
                "code\n", "code\n",
                "Convert", "GetTime"
            )
            with open(path, "r", encoding="utf-8") as f:
                result = f.read()
            self.assertEqual(result, original)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
