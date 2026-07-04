"""
Unit tests for arxml_processor module.

Tests cover:
  - extract_value: regex parsing of ARXML content
  - process_arxml: validation, integer conversion, doubling
"""

import os
import tempfile
import unittest

from wcs_modules.arxml_processor import extract_value, process_arxml


# ---------------------------------------------------------------------------
# Realistic ARXML content used by several tests
# ---------------------------------------------------------------------------
_VALID_ARXML = """\
<?xml version="1.0" encoding="utf-8"?>
<AUTOSAR>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>Fmy</SHORT-NAME>
      <DEFINITION-REF DEST="ECUC-PARAM-CONF-CONTAINER-DEF">/Some/Path</DEFINITION-REF>
      <PARAMETER-VALUES>
        <ECUC-NUMERICAL-PARAM-VALUE>
          <DEFINITION-REF DEST="ECUC-INTEGER-PARAM-DEF">/Some/Path/NrFmy</DEFINITION-REF>
          <VALUE>5</VALUE>
        </ECUC-NUMERICAL-PARAM-VALUE>
      </PARAMETER-VALUES>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
"""

_NO_MATCH_ARXML = """\
<?xml version="1.0" encoding="utf-8"?>
<AUTOSAR>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>SomethingElse</SHORT-NAME>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
"""


class TestExtractValue(unittest.TestCase):
    """Tests for extract_value()."""

    def test_valid_arxml_returns_value(self):
        """Extracts '5' from a realistic ARXML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".arxml",
                                         delete=False, encoding="utf-8") as f:
            f.write(_VALID_ARXML)
            path = f.name
        try:
            result = extract_value(path)
            self.assertEqual(result, ["5"])
        finally:
            os.unlink(path)

    def test_no_match_returns_empty(self):
        """Returns empty list when pattern is absent."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".arxml",
                                         delete=False, encoding="utf-8") as f:
            f.write(_NO_MATCH_ARXML)
            path = f.name
        try:
            result = extract_value(path)
            self.assertEqual(result, [])
        finally:
            os.unlink(path)

    def test_empty_file_returns_empty(self):
        """Returns empty list for an empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".arxml",
                                         delete=False, encoding="utf-8") as f:
            f.write("")
            path = f.name
        try:
            result = extract_value(path)
            self.assertEqual(result, [])
        finally:
            os.unlink(path)


class TestProcessArxml(unittest.TestCase):
    """Tests for process_arxml()."""

    def test_valid_returns_val_and_double(self):
        """Returns (5, 10) for VALUE=5."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".arxml",
                                         delete=False, encoding="utf-8") as f:
            f.write(_VALID_ARXML)
            path = f.name
        try:
            val, val_x_2 = process_arxml(path)
            self.assertEqual(val, 5)
            self.assertEqual(val_x_2, 10)
        finally:
            os.unlink(path)

    def test_no_match_returns_none_tuple(self):
        """Returns (None, None) when regex finds nothing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".arxml",
                                         delete=False, encoding="utf-8") as f:
            f.write(_NO_MATCH_ARXML)
            path = f.name
        try:
            val, val_x_2 = process_arxml(path)
            self.assertIsNone(val)
            self.assertIsNone(val_x_2)
        finally:
            os.unlink(path)

    def test_non_digit_value_returns_none(self):
        """Returns (None, None) when the extracted value is not a digit."""
        content = _VALID_ARXML.replace("<VALUE>5</VALUE>", "<VALUE>abc</VALUE>")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".arxml",
                                         delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            val, val_x_2 = process_arxml(path)
            self.assertIsNone(val)
            self.assertIsNone(val_x_2)
        finally:
            os.unlink(path)

    def test_value_one(self):
        """Edge case: VALUE=1 -> (1, 2)."""
        content = _VALID_ARXML.replace("<VALUE>5</VALUE>", "<VALUE>1</VALUE>")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".arxml",
                                         delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            val, val_x_2 = process_arxml(path)
            self.assertEqual(val, 1)
            self.assertEqual(val_x_2, 2)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
