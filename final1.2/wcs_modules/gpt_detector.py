"""
GPT Function Detection Module

Handles detection of GPT timing functions in header files.
"""

import os
import re
from typing import Optional, Tuple

from .logging_config import get_logger

logger = get_logger(__name__)

# Pre-compiled regex patterns for GPT functions
_CONVERT_PATTERNS = {
    'Gpt_ConvertTicksToMicrosec': re.compile(r'extern\s+uint32\s+Gpt_ConvertTicksToMicrosec\b'),
    'Iopt_Gpt_ConvertTicksToMicrosec': re.compile(r'extern\s+uint32\s+Iopt_Gpt_ConvertTicksToMicrosec\b')
}
_GETTIME_PATTERNS = {
    'Gpt_GetSystemTime': re.compile(r'extern\s+uint32\s+Gpt_GetSystemTime\b'),
    'Iopt_Gpt_GetSystemTime': re.compile(r'extern\s+uint32\s+Iopt_Gpt_GetSystemTime\b')
}


def find_function_pair_in_headers(root_folder: str) -> Optional[Tuple[str, str]]:
    """
    Searches for Gpt_ConvertTicksToMicrosec OR Iopt_Gpt_ConvertTicksToMicrosec
    and Gpt_GetSystemTime OR Iopt_Gpt_GetSystemTime functions in header files.
    
    Args:
        root_folder: Root directory to start the search
        
    Returns:
        Tuple of (convert_function_name, gettime_function_name) or None
    """
    found_convert = None
    found_gettime = None

    # Search through all .h files
    for dirpath, _, filenames in os.walk(root_folder):
        # Early continue if both found
        if found_convert and found_gettime:
            break
            
        for filename in filenames:
            if not filename.endswith('.h'):
                continue
                
            file_path = os.path.join(dirpath, filename)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                    # Search for convert function if not found yet
                    if not found_convert:
                        for name, pattern in _CONVERT_PATTERNS.items():
                            if pattern.search(content):
                                found_convert = name
                                break

                    # Search for gettime function if not found yet
                    if not found_gettime:
                        for name, pattern in _GETTIME_PATTERNS.items():
                            if pattern.search(content):
                                found_gettime = name
                                break

                    # Stop searching if both found
                    if found_convert and found_gettime:
                        break
            except Exception as e:
                logger.error("Could not read %s: %s", file_path, e)

    if found_convert and found_gettime:
        logger.info("Found convert function: %s", found_convert)
        logger.info("Found gettime function: %s", found_gettime)
        return (found_convert, found_gettime)

    # If either function not found, ask user for input
    logger.warning("Required functions not found in .h files.")
    return _prompt_for_functions(found_convert, found_gettime)


def _prompt_for_functions(found_convert: Optional[str], found_gettime: Optional[str]) -> Optional[Tuple[str, str]]:
    """
    Prompts user to input missing GPT function names.
    
    Args:
        found_convert: Already found convert function (or None)
        found_gettime: Already found gettime function (or None)
        
    Returns:
        Tuple of (convert_function, gettime_function) or None if cancelled
    """
    import tkinter as tk
    from tkinter import simpledialog, messagebox

    root = tk.Tk()
    root.withdraw()  # Hide main window

    # Prompt for convert function if not found
    if not found_convert:
        found_convert = simpledialog.askstring(
            "Convert Function",
            "Enter the name of ConvertTicksToMicrosec function (e.g., Gpt_ConvertTicksToMicrosec):"
        )
        if found_convert:
            found_convert = found_convert.strip()
        else:
            messagebox.showwarning("Warning", "Convert function was not entered!")

    # Prompt for gettime function if not found
    if not found_gettime:
        found_gettime = simpledialog.askstring(
            "GetTime Function",
            "Enter the name of GetSystemTime function (e.g., Gpt_GetSystemTime):"
        )
        if found_gettime:
            found_gettime = found_gettime.strip()
        else:
            messagebox.showwarning("Warning", "GetTime function was not entered!")

    root.destroy()

    if found_convert and found_gettime:
        logger.info("User provided - Convert: %s, GetTime: %s", found_convert, found_gettime)
        return (found_convert, found_gettime)
    
    return None
