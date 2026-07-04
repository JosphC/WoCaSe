"""
XML/CBD File Modifier Module

Handles modification of XML, CBD files.
"""

import os
from typing import Optional
from . import templates, path_utils
from .logging_config import get_logger

logger = get_logger(__name__)

# Constants
_CBD_SEARCH_STRINGS = ['icsp_dem_test_genr.xml', 'icsp_dem_test.h']
_CBD_FILENAMES = ["icsp_dem_cnf.cbd", "icsp_dem_cnf_sw.cbd"]
_XML_GENR_FILENAME = "icsp_dem_test_genr.xml"


def insert_after_first_filedefinition(filename: str, block: str) -> None:
    """
    Inserts code after the first </FileDefinition> in a CBD file.
    
    Args:
        filename: Path to the CBD file
        block: XML content to insert
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()

        # Find first occurrence of </FileDefinition>
        tag = '</FileDefinition>'
        idx = content.find(tag)
        if idx == -1:
            logger.warning("No </FileDefinition> found! Nothing inserted.")
            return

        # Insert block after the tag
        idx += len(tag)
        new_content = content[:idx] + block + content[idx:]

        # Set write permissions (best-effort — may fail on Windows with ACLs)
        try:
            os.chmod(filename, 0o666)
        except Exception as exc:
            logger.debug("chmod failed for %r: %s", filename, exc)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(new_content)
        logger.info("Block inserted after first </FileDefinition> in '%s'.", filename)
        
    except IOError as e:
        logger.error("Error modifying file %s: %s", filename, e)



def already_inserted(filename: str, search_strings: list) -> bool:
    """
    Checks if specified strings already exist in the file.
    
    Args:
        filename: Path to the file to check
        search_strings: List of strings to search for
        
    Returns:
        True if all strings found, False otherwise
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        return all(s in content for s in search_strings)
    except FileNotFoundError:
        logger.error("File not found: %s", filename)
        return False
    except Exception as e:
        logger.error("Error checking file %s: %s", filename, e)
        return False


def modify_icsp_dem_cbd(cbd_file_path: str) -> None:
    """
    Modifies icsp_dem.cbd file to add icsp_dem_test_genr.xml and icsp_dem_test.h.
    
    Args:
        cbd_file_path: Path to the icsp_dem.cbd file
    """
    # Check if already inserted
    if already_inserted(cbd_file_path, _CBD_SEARCH_STRINGS):
        logger.info("Files already added to %s", cbd_file_path)
        return
    
    code_to_insert = templates.get_cbd_insert_block()
    insert_after_first_filedefinition(cbd_file_path, code_to_insert)


def find_cbd_file(case_name: str) -> Optional[str]:
    """
    Searches for the first existing .cbd configuration file in the current project.
    
    Args:
        case_name: Path to the case directory
        
    Returns:
        Path to .cbd file or None if not found
    """
    for name in _CBD_FILENAMES:
        cbd_path = path_utils.find_project_file(name, case_name)
        if cbd_path and os.path.exists(cbd_path):   
            logger.info("Found .cbd file: %s", cbd_path)
            return cbd_path
    logger.error("No .cbd file found for this project!")
    return None


def path_insert_xml(case_name: str) -> None:
    """
    Creates icsp_dem_test_genr.xml in the appropriate project directory.
    
    Args:
        case_name: Path to the case directory
    """
    logger.info("-" * 80)
    
    # Check if XML already exists
    dest_file = path_utils.find_project_file(_XML_GENR_FILENAME, case_name)
    if dest_file and os.path.exists(dest_file):
        logger.info("XML file already exists at %s. Will not overwrite.", dest_file)
        return

    # Find CBD file to determine destination directory
    cbd_path = find_cbd_file(case_name)
    if not cbd_path:
        logger.error("Could not locate a .cbd file. Cannot determine where to create XML.")
        return

    # Create XML file
    dest_file = os.path.join(os.path.dirname(cbd_path), _XML_GENR_FILENAME)
    logger.info("Creating XML file at: %s", dest_file)

    try:
        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(templates.get_xml_genr_template())
        logger.info("XML file created successfully")
    except IOError as e:
        logger.error("Could not create XML file: %s", e)

