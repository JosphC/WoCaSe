"""
Unit tests for templates module.

Tests cover:
  - get_dcnfxml_template: parameter substitution and XML structure
  - get_grl_template: parameter substitution
  - get_cbd_template: static content
  - get_xml_genr_template: static content
  - get_cbd_insert_block: static content
  - get_runtime_check_start: code generation with parameters
  - get_runtime_check_end: code generation with parameters
"""

import unittest

from wcs_modules.templates import (
    get_dcnfxml_template,
    get_grl_template,
    get_cbd_template,
    get_xml_genr_template,
    get_cbd_insert_block,
    get_runtime_check_start,
    get_runtime_check_end,
)


class TestGetDcnfxmlTemplate(unittest.TestCase):
    """Tests for get_dcnfxml_template()."""

    def test_contains_val_double(self):
        result = get_dcnfxml_template(18)
        self.assertIn("<array-dimension-maximum>18</array-dimension-maximum>", result)

    def test_contains_xml_header(self):
        result = get_dcnfxml_template(5)
        self.assertIn("<?xml version=", result)

    def test_contains_wcs_diag(self):
        result = get_dcnfxml_template(5)
        self.assertIn("WCS_DIAG", result)

    def test_contains_nc_nr_wcs_test(self):
        result = get_dcnfxml_template(5)
        self.assertIn("NC_NR_WCS_TEST", result)


class TestGetGrlTemplate(unittest.TestCase):
    """Tests for get_grl_template()."""

    def test_contains_value(self):
        result = get_grl_template(42)
        self.assertIn("value = 42;", result)

    def test_contains_nc_nr(self):
        result = get_grl_template(10)
        self.assertIn("NC_NR_WCS_TEST", result)

    def test_contains_file_definitions(self):
        result = get_grl_template(10)
        self.assertIn("errm_wcs_data.c", result)
        self.assertIn("errm_wcs_priv.h", result)
        self.assertIn("errm_wcs_pub.h", result)


class TestGetCbdTemplate(unittest.TestCase):
    """Tests for get_cbd_template()."""

    def test_contains_xml_header(self):
        result = get_cbd_template()
        self.assertIn("<?xml version=", result)

    def test_contains_composite_name(self):
        result = get_cbd_template()
        self.assertIn("errm_wcs_test", result)

    def test_contains_grl_reference(self):
        result = get_cbd_template()
        self.assertIn("errm_wcs.grl", result)

    def test_contains_dcnfxml_reference(self):
        result = get_cbd_template()
        self.assertIn("errm_wcs.dcnfxml", result)


class TestGetXmlGenrTemplate(unittest.TestCase):
    """Tests for get_xml_genr_template()."""

    def test_contains_root_element(self):
        result = get_xml_genr_template()
        self.assertIn("<root", result)

    def test_contains_calibration_variables(self):
        result = get_xml_genr_template()
        self.assertIn("lc_enable_runtime_dem_main", result)
        self.assertIn("lc_enable_next_nr_fmy_events", result)
        self.assertIn("lc_enable_first_nr_fmy_events", result)

    def test_contains_debug_variables(self):
        result = get_xml_genr_template()
        self.assertIn("debug_dem_diags_on", result)
        self.assertIn("debug_dem_highest_time", result)


class TestGetCbdInsertBlock(unittest.TestCase):
    """Tests for get_cbd_insert_block()."""

    def test_contains_xml_filename(self):
        result = get_cbd_insert_block()
        self.assertIn("icsp_dem_test_genr.xml", result)

    def test_contains_header_filename(self):
        result = get_cbd_insert_block()
        self.assertIn("icsp_dem_test.h", result)

    def test_contains_filedefinition_tags(self):
        result = get_cbd_insert_block()
        self.assertIn("<FileDefinition>", result)
        self.assertIn("</FileDefinition>", result)


class TestGetRuntimeCheckStart(unittest.TestCase):
    """Tests for get_runtime_check_start()."""

    def test_contains_variable_declarations(self):
        result = get_runtime_check_start(3, "ConvertFunc", "GetTimeFunc")
        self.assertIn("uint32 tmp_time;", result)
        self.assertIn("uint32 tmp_time_old;", result)
        self.assertIn("uint32 tmp_time_new;", result)

    def test_contains_correct_number_of_diags_first_block(self):
        """First block has fmy diagnostics (0 to fmy-1)."""
        result = get_runtime_check_start(3, "Conv", "GetT")
        self.assertIn("NC_IDX_ERR_WCS_DIAG_0", result)
        self.assertIn("NC_IDX_ERR_WCS_DIAG_1", result)
        self.assertIn("NC_IDX_ERR_WCS_DIAG_2", result)

    def test_contains_correct_number_of_diags_second_block(self):
        """Second block has fmy diagnostics (fmy to 2*fmy-1)."""
        result = get_runtime_check_start(3, "Conv", "GetT")
        self.assertIn("NC_IDX_ERR_WCS_DIAG_3", result)
        self.assertIn("NC_IDX_ERR_WCS_DIAG_4", result)
        self.assertIn("NC_IDX_ERR_WCS_DIAG_5", result)

    def test_contains_function_calls(self):
        result = get_runtime_check_start(1, "MyConvert", "MyGetTime")
        self.assertIn("tmp_time_old = MyConvert(MyGetTime())", result)

    def test_total_diag_count(self):
        """Total diagnostics = 2 * fmy."""
        fmy = 4
        result = get_runtime_check_start(fmy, "C", "G")
        count = result.count("ACTION_ERRM_ResultDiag")
        self.assertEqual(count, fmy * 2)


class TestGetRuntimeCheckEnd(unittest.TestCase):
    """Tests for get_runtime_check_end()."""

    def test_contains_time_calculation(self):
        result = get_runtime_check_end("ConvertFunc", "GetTimeFunc")
        self.assertIn("tmp_time_new = ConvertFunc(GetTimeFunc())", result)

    def test_contains_highest_time_update(self):
        result = get_runtime_check_end("C", "G")
        self.assertIn("debug_dem_highest_time", result)

    def test_contains_comparison_logic(self):
        result = get_runtime_check_end("C", "G")
        self.assertIn("tmp_time_new > tmp_time_old", result)
        self.assertIn("tmp_time > debug_dem_highest_time", result)


if __name__ == "__main__":
    unittest.main()
