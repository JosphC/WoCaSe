"""
Source Code Modifier Module

Handles modification of C source files (main.c) with runtime checks.
"""

import os
import re
from typing import List
from . import templates
from .logging_config import get_logger

logger = get_logger(__name__)


def insert_headers_after_last_include(filename: str, new_headers: List[str]) -> None:
    """
    Inserts new header includes after the last #include in the file.
    
    Args:
        filename: Path to the C file
        new_headers: List of header includes to add (e.g., ['#include "file.h"'])
    """
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    found_first_include = False
    last_include_idx = -1
    idx = 0
    n = len(lines)
    while idx < n:
        line = lines[idx]
        if not found_first_include:
            # Find the first #include
            if line.strip().startswith('#include'):
                found_first_include = True
                last_include_idx = idx
        else:
            # After the first include was found
            # Skip comments and blank lines
            next_non_comment_idx = idx
            while next_non_comment_idx < n and is_comment(lines[next_non_comment_idx]):
                next_non_comment_idx += 1
            if next_non_comment_idx < n and lines[next_non_comment_idx].strip().startswith('#include'):
                last_include_idx = next_non_comment_idx
                idx = next_non_comment_idx
            else:
                # Not an include, so break: we found where to insert
                break
        idx += 1

    headers_to_insert = []
    for h in new_headers:
        if not any(h.strip() == l.strip() for l in lines):
            headers_to_insert.append(h if h.endswith('\n') else h + '\n')

    insert_idx = last_include_idx + 1  # Insert after the last include block
    new_lines = lines[:insert_idx] + headers_to_insert + lines[insert_idx:]


    try:
        os.chmod(filename, 0o666)
    except Exception as e:
        logger.error("Could not change the permission of the file main (include): %s", e)

    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    logger.info("Inserted headers %s in file %s.", [h.strip() for h in headers_to_insert], filename)

def insert_code_in_function(
    filename: str,
    function_name: str,
    code_to_insert: str,
    end_code_to_insert: str,
    convert_func: str,
    gettime_func: str
) -> bool:
    """
    Inserts runtime check code at the start and end of a function.
    
    Args:
        filename: Path to the C file
        function_name: Name of the function to modify (e.g., 'main')
        code_to_insert: Code to insert at function start
        end_code_to_insert: Code to insert before function end
        convert_func: Name of convert ticks function
        gettime_func: Name of get system time function
    """
    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Build regex for function header
    func_pattern = re.compile(r'^\s*void\s+' + re.escape(function_name) + r'\s*\(\s*void\s*\)\s*')
    # Pattern for start of function implementation
    open_brace_pattern = re.compile(r'^\s*\{')

    found_func = False
    inside_func = False
    func_start_idx = -1
    func_end_idx = -1

    # Find function start and end
    for idx, line in enumerate(lines):
        if not found_func and func_pattern.match(line):
            found_func = True
            # Seek to the brace
            for j in range(idx+1, len(lines)):
                if open_brace_pattern.match(lines[j]):
                    # Function body starts at j
                    func_start_idx = j
                    inside_func = True
                    break
        if found_func and inside_func:
            # Find the matching closing brace
            brace_count = 0
            for j in range(func_start_idx, len(lines)):
                brace_count += lines[j].count('{')
                brace_count -= lines[j].count('}')
                if brace_count == 0:
                    func_end_idx = j
                    break
            break

    if func_start_idx == -1 or func_end_idx == -1:
        logger.error("Function '%s' not found or braces don't match!", function_name)
        return False

    signature_block = [
        "uint32 tmp_time;",
        "uint32 tmp_time_old;",
        "uint32 tmp_time_new;"
    ]
    already_start = lines_block_exists(lines, func_start_idx, func_end_idx, signature_block)
    end_signature_line = f"tmp_time_new = {convert_func}({gettime_func}());"
    already_end = any(end_signature_line in lines[i] for i in range(func_start_idx+1, func_end_idx))

    if already_start or already_end:
        logger.info("Code block(s) already present in function '%s'! Not inserting duplicates.", function_name)
        return True
    
    if already_start != already_end:
        logger.warning(
            "Partial runtime check code found in function '%s'. Manual review recommended.",
            function_name
        )
        return False

    # Insert at start (RIGHT AFTER opening brace)
    indent_start = re.match(r'^(\s*)', lines[func_start_idx]).group(1)
    code_to_insert_indented = ''.join(
        [indent_start + l if l.strip() else l for l in code_to_insert.splitlines(True)]
    )

    # Insert at end (RIGHT BEFORE final closing brace)
    indent_end = re.match(r'^(\s*)', lines[func_end_idx]).group(1)
    end_code_to_insert_indented = ''.join(
        [indent_end + l if l.strip() else l for l in end_code_to_insert.splitlines(True)]
    )

    # Compose new lines
    new_lines = []
    for idx, line in enumerate(lines):
        if idx == func_start_idx:
            new_lines.append(line)
            new_lines.append(code_to_insert_indented)
        elif idx == func_end_idx:
            # Insert end code before final }
            new_lines.append(end_code_to_insert_indented)
            new_lines.append(line)
        else:
            new_lines.append(line)

    try:
        os.chmod(filename, 0o666)
    except Exception as e:
        logger.error("Could not change the permission of the file main (code): %s", e)
    with open(filename, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    logger.info("Inserted start and end code in '%s' in '%s'.", function_name, filename)
    return True


def modify_main_c(file_path: str, fmy: int, convert_func: str, gettime_func: str) -> None:
    """
    Modifies the main.c file by injecting runtime check code.
    
    Args:
        file_path: Path to the main.c file
        fmy: Number of diagnostic events in each block
        convert_func: Name of the convert ticks function
        gettime_func: Name of the get system time function
    """
    # Generate code snippets
    start_code = templates.get_runtime_check_start(fmy, convert_func, gettime_func)
    end_code = templates.get_runtime_check_end(convert_func, gettime_func)

    possible_function_names = [
        'Icsp_Dem_MainFunction',
        'Dem_MainFunction',
    ]
    
    # Insert code into main function
    # insert_code_in_function(
    #     file_path,
    #     'Icsp_Dem_MainFunction',
    #     start_code,
    #     end_code,
    #     convert_func,
    #     gettime_func
    # )
    for function_name in possible_function_names:
        modified = insert_code_in_function(
            file_path,
            function_name,
            start_code,
            end_code,
            convert_func,
            gettime_func
        )
        if modified:
            logger.info("Modified function '%s' successfully.", function_name)
            return
    
    logger.error("None of the target functions were found or modified in '%s'.", file_path)


def add_headers_to_main_c(file_path: str) -> None:
    """
    Adds necessary header includes to main.c if they don't already exist.
    
    Args:
        file_path: Path to the main.c file
    """
    headers_to_add = [
        '#include "icsp_dem_test.h"',
        '#include "errm_genr.h"'
    ]
    
    insert_headers_after_last_include(file_path, headers_to_add)


def is_comment(line: str) -> bool:
    """
    Checks whether a line is a comment or is empty.
    
    Args:
        line: Line of code to check
        
    Returns:
        True if line is comment or empty, False otherwise
    """
    stripped = line.strip()
    return (
        stripped.startswith('//') or
        stripped.startswith('/*') or
        stripped.startswith('*') or
        stripped.endswith('*/') or
        stripped == ''
    )


def lines_block_exists(lines: List[str], func_start: int, func_end: int, block: List[str]) -> bool:
    """
    Checks if a given block of lines appears consecutively within a specified range of lines.
    
    Args:
        lines: All lines from the file
        func_start: Start index of function
        func_end: End index of function
        block: Block of lines to search for
        
    Returns:
        True if block exists, False otherwise
    """
    block_len = len(block)
    for idx in range(func_start + 1, func_end - block_len + 2):
        match = True
        for off, tst in enumerate(block):
            if tst.strip() != lines[idx + off].strip():
                match = False
                break
        if match:
            return True
    return False
