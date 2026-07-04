"""
Path Utilities Module

Handles project path creation and directory searching.
"""

import os
from typing import Optional

from .logging_config import get_logger

logger = get_logger(__name__)


def create_case_path(case_name: str, base_dir: str = r'd:\casdev\td5') -> Optional[str]:
    """
    Creates and returns the full path for a project or release based on naming convention.
    
    Examples:
        - 'PROJ6_0U0_000' -> d:/casdev/td5/PR/OJ6/000/PROJ6_0U0_000
        - 'PROJ2_0U0_OB6_024' -> d:/casdev/td5/PR/OJ2/OB6/PROJ2_0U0_OB6_024
        - 'PROJ5_000U0' -> d:/casdev/td5/PR/OJ5/PROJ5_000U0
        - 'FOH12_0U0' -> d:/casdev/td5/FO/H12/0U0/FOH12_0U0
    
    Args:
        case_name: Project or release name
        base_dir: Base directory for TD5 projects
        
    Returns:
        Full path to the project directory or None if format is invalid
    """
    parts = case_name.split('_')
    first_part = parts[0] if parts else ""
    
    if len(first_part) != 5:
        logger.error("Invalid project/release format: %s", case_name)
        return None
    
    brand = first_part[:2]
    platform = first_part[2:]
    
    if len(parts) == 2:
        suffix = parts[1]
        if len(suffix) > 3:
            return os.path.join(base_dir, brand, platform, case_name)
        elif len(suffix) == 3:
            return os.path.join(base_dir, brand, platform, suffix, case_name)
        else:
            logger.error("Invalid suffix format: %s", case_name)
            return None
    elif len(parts) in (3, 4):
        return os.path.join(base_dir, brand, platform, parts[2], case_name)

    logger.error("Invalid project/release format: %s", case_name)
    return None


def find_first_work_subdir(path: str) -> Optional[str]:
    """
    Recursively searches for the first directory named 'work' (case-insensitive) under the given path.
    
    Args:
        path: Starting path to search from
        
    Returns:
        Full path to the first 'work' directory found, or None if not found
    """
    path = os.path.normpath(path)
    try:
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False) and entry.name.casefold() == "work":
                    return entry.path
    except (FileNotFoundError, PermissionError):
        return None
    return None


def find_folder(root_path: str, target_folder: str) -> Optional[str]:
    """
    Searches recursively for a folder with a specific relative path structure.
    Accepts both forward slash (/) and backslash (\\) as separators.
    
    Args:
        root_path: Root path to search in
        target_folder: Target folder path pattern (e.g., 'errm_fctdg_test\\i' or 'Dem/cnf')
        
    Returns:
        Full path to the matching folder or None if not found
    """
    # Normalize separators - accept both / and \
    target_parts = target_folder.replace('/', '\\').split('\\')
    
    for dirpath, _, _ in os.walk(root_path):
        rel_path = os.path.relpath(dirpath, root_path)
        rel_parts = rel_path.split(os.sep)
        
        if rel_parts[-len(target_parts):] == target_parts:
            return dirpath
    return None

def find_project_file(file_name: str, case_path: str) -> Optional[str]:
    """
    Finds the first 'work' directory under case_path, then recursively searches
    inside that 'work' directory for a file named file_name (case-insensitive).
    
    Args:
        file_name: Name of the file to search for
        case_path: Starting path to search from
        
    Returns:
        Absolute path if found, otherwise None
    """
    work_dir = find_first_work_subdir(case_path)
    if not work_dir:
        logger.warning("No 'work' subdirectory found in %s", case_path)
        return None
    
    file_name_lower = file_name.lower()
    for dirpath, _, filenames in os.walk(work_dir):
        for filename in filenames:
            if filename.lower() == file_name_lower:
                return os.path.join(dirpath, filename)
    return None
