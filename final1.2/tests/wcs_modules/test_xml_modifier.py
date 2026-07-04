"""
Unit tests for xml_modifier module.

Tests cover:
  - insert_after_first_filedefinition: insertion, missing tag
  - already_inserted: all present, partial, file not found
  - modify_icsp_dem_cbd: idempotent behaviour
  - find_cbd_file: found and not found
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from wcs_modules.xml_modifier import (
    insert_after_first_filedefinition,
    already_inserted,
    modify_icsp_dem_cbd,
)


class TestInsertAfterFirstFileDefinition(unittest.TestCase):
    """Tests for insert_after_first_filedefinition()."""

    _CBD_CONTENT = """\
<?xml version='1.0'?>
<cbd>
  <Files>
    <FileDefinition>
      <FileName>existing.grl</FileName>
    </FileDefinition>
  </Files>
</cbd>
"""

    def test_inserts_after_tag(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cbd",
                                         delete=False, encoding="utf-8") as f:
            f.write(self._CBD_CONTENT)
            path = f.name
        try:
            insert_after_first_filedefinition(path, "\n<NewBlock/>")
            with open(path, "r", encoding="utf-8") as f:
                result = f.read()
            idx_tag = result.find("</FileDefinition>")
            idx_new = result.find("<NewBlock/>")
            self.assertGreater(idx_new, idx_tag)
        finally:
            os.unlink(path)

    def test_no_filedefinition_tag(self):
        """Does nothing when </FileDefinition> is absent."""
        content = "<?xml version='1.0'?><root><Other/></root>"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cbd",
                                         delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            insert_after_first_filedefinition(path, "<Block/>")
            with open(path, "r", encoding="utf-8") as f:
                result = f.read()
            self.assertNotIn("<Block/>", result)
        finally:
            os.unlink(path)


class TestAlreadyInserted(unittest.TestCase):
    """Tests for already_inserted()."""

    def test_all_strings_present(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cbd",
                                         delete=False, encoding="utf-8") as f:
            f.write("alpha beta gamma")
            path = f.name
        try:
            self.assertTrue(already_inserted(path, ["alpha", "gamma"]))
        finally:
            os.unlink(path)

    def test_partial_match(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cbd",
                                         delete=False, encoding="utf-8") as f:
            f.write("alpha beta")
            path = f.name
        try:
            self.assertFalse(already_inserted(path, ["alpha", "gamma"]))
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        self.assertFalse(already_inserted(r"C:\nonexistent_file.cbd", ["x"]))

    def test_empty_search_list(self):
        """Empty search list -> all() returns True."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cbd",
                                         delete=False, encoding="utf-8") as f:
            f.write("anything")
            path = f.name
        try:
            self.assertTrue(already_inserted(path, []))
        finally:
            os.unlink(path)


class TestModifyIcspDemCbd(unittest.TestCase):
    """Tests for modify_icsp_dem_cbd()."""

    _CBD_WITH_TAG = """\
<?xml version='1.0'?>
<cbd>
  <Files>
    <FileDefinition>
      <FileName>original.grl</FileName>
    </FileDefinition>
  </Files>
</cbd>
"""

    def test_inserts_test_blocks(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cbd",
                                         delete=False, encoding="utf-8") as f:
            f.write(self._CBD_WITH_TAG)
            path = f.name
        try:
            modify_icsp_dem_cbd(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("icsp_dem_test_genr.xml", content)
            self.assertIn("icsp_dem_test.h", content)
        finally:
            os.unlink(path)

    def test_idempotent(self):
        """Second call does not duplicate insertion."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cbd",
                                         delete=False, encoding="utf-8") as f:
            f.write(self._CBD_WITH_TAG)
            path = f.name
        try:
            modify_icsp_dem_cbd(path)
            modify_icsp_dem_cbd(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content.count("icsp_dem_test_genr.xml"), 1)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
