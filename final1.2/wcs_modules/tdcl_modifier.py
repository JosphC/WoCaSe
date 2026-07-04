"""
TDCL File Modifier Module

Handles modification of TDCL configuration files.
"""

import os
import stat
from typing import Optional

from .logging_config import get_logger

logger = get_logger(__name__)

# Constants
_INCLUDE_LINE = "#include <errm_wcs_test_cbd.tdcl>"
_TARGET_FILENAMES = ("project_options.tdcl", "errm.tdcl", "errm_agf.tdcl")


def _line_present(content: str, target: str) -> bool:
    """Check whether *target* appears as a standalone line in *content*."""
    for line in content.splitlines():
        if line.strip() == target:
            return True
    return False


def find_and_insert_errm_include(base_dir: str) -> Optional[str]:
    """Locate a TDCL configuration file and insert the ERRM include if missing.

    Walks the directory tree once, picks the highest-priority file, checks
    if the include already exists, and inserts it after the first line if not.

    Args:
        base_dir: Root directory to search recursively for TDCL files.

    Returns:
        The absolute path of the file, or None if no TDCL file was found.
    """
    _priority = {name: idx for idx, name in enumerate(_TARGET_FILENAMES)}
    best_priority = len(_TARGET_FILENAMES)
    best_path: Optional[str] = None

    for root, dirs, files in os.walk(base_dir, topdown=True):
        for filename in files:
            if filename not in _priority:
                continue
            prio = _priority[filename]
            if prio < best_priority:
                best_priority = prio
                best_path = os.path.join(root, filename)
            if best_priority == 0:
                break
        if best_priority == 0:
            dirs.clear()
            break

    if best_path is None:
        logger.warning("No TDCL file found in %s", base_dir)
        return None

    try:
        with open(best_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if _line_present(content, _INCLUDE_LINE):
            logger.info("Include already exists in %s", best_path)
            return best_path

        try:
            os.chmod(best_path, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass

        include_line = _INCLUDE_LINE + "\n"

        if content == "":
            new_content = include_line
        else:
            first_nl_pos = content.find("\n")
            if first_nl_pos == -1:
                new_content = content + "\n" + include_line
            else:
                new_content = (
                    content[:first_nl_pos + 1]
                    + include_line
                    + content[first_nl_pos + 1:]
                )

        with open(best_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        logger.info("Include inserted in %s", best_path)
        return best_path

    except IOError as e:
        logger.error("Error processing %s: %s", best_path, e)
        return None




