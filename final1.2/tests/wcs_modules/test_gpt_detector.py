"""
Unit tests for gpt_detector module.

Tests cover:
  - find_function_pair_in_headers:
      • both functions found
      • only one found (falls through to prompt)
      • neither found
      • Iopt_ variants
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from wcs_modules.gpt_detector import find_function_pair_in_headers


class TestFindFunctionPairInHeaders(unittest.TestCase):
    """Tests for find_function_pair_in_headers()."""

    def _create_header(self, directory: str, filename: str, content: str) -> str:
        filepath = os.path.join(directory, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def test_both_functions_found(self):
        """Returns (convert, gettime) when both are found."""
        with tempfile.TemporaryDirectory() as tmp:
            self._create_header(tmp, "gpt.h", (
                "extern uint32 Gpt_ConvertTicksToMicrosec(uint32 ticks);\n"
                "extern uint32 Gpt_GetSystemTime(void);\n"
            ))
            result = find_function_pair_in_headers(tmp)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], "Gpt_ConvertTicksToMicrosec")
            self.assertEqual(result[1], "Gpt_GetSystemTime")

    def test_iopt_variants_found(self):
        """Returns Iopt_ variants when those are present."""
        with tempfile.TemporaryDirectory() as tmp:
            self._create_header(tmp, "iopt_gpt.h", (
                "extern uint32 Iopt_Gpt_ConvertTicksToMicrosec(uint32 ticks);\n"
                "extern uint32 Iopt_Gpt_GetSystemTime(void);\n"
            ))
            result = find_function_pair_in_headers(tmp)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], "Iopt_Gpt_ConvertTicksToMicrosec")
            self.assertEqual(result[1], "Iopt_Gpt_GetSystemTime")

    @patch("wcs_modules.gpt_detector._prompt_for_functions", return_value=None)
    def test_neither_found_returns_none(self, mock_prompt):
        """Returns None when no functions found and user cancels prompt."""
        with tempfile.TemporaryDirectory() as tmp:
            self._create_header(tmp, "other.h", "int some_function(void);\n")
            result = find_function_pair_in_headers(tmp)
            self.assertIsNone(result)
            mock_prompt.assert_called_once()

    @patch("wcs_modules.gpt_detector._prompt_for_functions", return_value=None)
    def test_only_convert_found(self, mock_prompt):
        """Falls through to prompt when only convert function is found."""
        with tempfile.TemporaryDirectory() as tmp:
            self._create_header(tmp, "gpt.h",
                                "extern uint32 Gpt_ConvertTicksToMicrosec(uint32 ticks);\n")
            result = find_function_pair_in_headers(tmp)
            self.assertIsNone(result)
            # Prompt was called with convert found, gettime None
            args = mock_prompt.call_args[0]
            self.assertEqual(args[0], "Gpt_ConvertTicksToMicrosec")
            self.assertIsNone(args[1])

    def test_non_h_files_ignored(self):
        """Only .h files are searched."""
        with tempfile.TemporaryDirectory() as tmp:
            self._create_header(tmp, "gpt.c", (
                "extern uint32 Gpt_ConvertTicksToMicrosec(uint32 ticks);\n"
                "extern uint32 Gpt_GetSystemTime(void);\n"
            ))
            with patch("wcs_modules.gpt_detector._prompt_for_functions", return_value=None):
                result = find_function_pair_in_headers(tmp)
                self.assertIsNone(result)

    def test_searches_subdirectories(self):
        """Recursively searches nested directories."""
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "deep", "nested")
            os.makedirs(sub)
            self._create_header(sub, "gpt.h", (
                "extern uint32 Gpt_ConvertTicksToMicrosec(uint32 ticks);\n"
                "extern uint32 Gpt_GetSystemTime(void);\n"
            ))
            result = find_function_pair_in_headers(tmp)
            self.assertIsNotNone(result)

    def test_empty_directory(self):
        """Returns None for empty directory."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("wcs_modules.gpt_detector._prompt_for_functions", return_value=None):
                result = find_function_pair_in_headers(tmp)
                self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
