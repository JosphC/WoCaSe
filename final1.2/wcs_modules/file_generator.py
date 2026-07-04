"""
File Generation Module

Handles creation of all configuration files (DCNFXML, GRL, CBD, XML).
"""

import os
from . import templates
from .logging_config import get_logger

logger = get_logger(__name__)


def _write_file(file_path: str, content: str) -> None:
    """Helper function to write content to a file."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    logger.info("File created: %s", file_path)


def create_errm_wcs_dcnfxml(output_dir: str, val_double: int) -> None:
    """
    Creates `errm_wcs.dcnfxml` file in `output_dir`.
    
    Args:
        output_dir: Directory where the file will be created
        val_double: Maximum array dimension value (val*2)
    """
    content = templates.get_dcnfxml_template(val_double)
    file_path = os.path.join(output_dir, 'errm_wcs.dcnfxml')
    _write_file(file_path, content)


def create_errm_wcs_grl(output_dir: str, val: int) -> None:
    """
    Creates `errm_wcs.grl` file in `output_dir`.
    
    Args:
        output_dir: Directory where the file will be created
        val: Value for NC_NR_WCS_TEST constant
    """
    content = templates.get_grl_template(val)
    file_path = os.path.join(output_dir, 'errm_wcs.grl')
    _write_file(file_path, content)


def create_cbd_file_at(folder_path: str) -> None:
    """
    Creates `errm_wcs_test.cbd` file in the specified folder.
    
    Args:
        folder_path: Directory where the CBD file will be created
    """
    content = templates.get_cbd_template()
    file_path = os.path.join(folder_path, "errm_wcs_test.cbd")
    _write_file(file_path, content)


def create_icsp_dem_test_genr_xml(output_dir: str) -> None:
    """
    Creates `icsp_dem_test_genr.xml` file in `output_dir`.
    
    Args:
        output_dir: Directory where the file will be created
    """
    content = templates.get_xml_genr_template()
    file_path = os.path.join(output_dir, 'icsp_dem_test_genr.xml')
    _write_file(file_path, content)
