"""
Unit tests for file_generator module.

Tests cover:
  - create_errm_wcs_dcnfxml: file creation and content
  - create_errm_wcs_grl: file creation and content
  - create_cbd_file_at: file creation and content
  - create_icsp_dem_test_genr_xml: file creation and content
"""

import os
import tempfile
import unittest

from wcs_modules.file_generator import (
    create_errm_wcs_dcnfxml,
    create_errm_wcs_grl,
    create_cbd_file_at,
    create_icsp_dem_test_genr_xml,
)


class TestCreateErrmWcsDcnfxml(unittest.TestCase):
    """Tests for create_errm_wcs_dcnfxml()."""

    def test_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_errm_wcs_dcnfxml(tmp, 9)
            path = os.path.join(tmp, "errm_wcs.dcnfxml")
            self.assertTrue(os.path.isfile(path))

    def test_content_contains_val_double(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_errm_wcs_dcnfxml(tmp, 14)
            path = os.path.join(tmp, "errm_wcs.dcnfxml")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<array-dimension-maximum>14</array-dimension-maximum>", content)

    def test_content_is_valid_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_errm_wcs_dcnfxml(tmp, 5)
            path = os.path.join(tmp, "errm_wcs.dcnfxml")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<?xml version=", content)
            self.assertIn("DiagnosticsConfiguration", content)


class TestCreateErrmWcsGrl(unittest.TestCase):
    """Tests for create_errm_wcs_grl()."""

    def test_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_errm_wcs_grl(tmp, 10)
            path = os.path.join(tmp, "errm_wcs.grl")
            self.assertTrue(os.path.isfile(path))

    def test_content_contains_val(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_errm_wcs_grl(tmp, 42)
            path = os.path.join(tmp, "errm_wcs.grl")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("value = 42;", content)

    def test_content_contains_nc_nr(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_errm_wcs_grl(tmp, 7)
            path = os.path.join(tmp, "errm_wcs.grl")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("NC_NR_WCS_TEST", content)


class TestCreateCbdFileAt(unittest.TestCase):
    """Tests for create_cbd_file_at()."""

    def test_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_cbd_file_at(tmp)
            path = os.path.join(tmp, "errm_wcs_test.cbd")
            self.assertTrue(os.path.isfile(path))

    def test_content_is_valid_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_cbd_file_at(tmp)
            path = os.path.join(tmp, "errm_wcs_test.cbd")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<?xml version=", content)
            self.assertIn("errm_wcs_test", content)


class TestCreateIcspDemTestGenrXml(unittest.TestCase):
    """Tests for create_icsp_dem_test_genr_xml()."""

    def test_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_icsp_dem_test_genr_xml(tmp)
            path = os.path.join(tmp, "icsp_dem_test_genr.xml")
            self.assertTrue(os.path.isfile(path))

    def test_content_has_root_element(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_icsp_dem_test_genr_xml(tmp)
            path = os.path.join(tmp, "icsp_dem_test_genr.xml")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<root", content)
            self.assertIn("lc_enable_runtime_dem_main", content)


if __name__ == "__main__":
    unittest.main()
