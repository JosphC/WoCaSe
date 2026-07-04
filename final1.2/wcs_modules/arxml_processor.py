"""
ARXML Processing Module

Handles parsing and processing of ARXML configuration files.
"""

import re
from typing import Optional, List, Tuple

from .logging_config import get_logger

logger = get_logger(__name__)


# Pre-compiled regex pattern for better performance
_FMY_PATTERN = re.compile(
    r"<SHORT-NAME>Fmy</SHORT-NAME>.*?"
    r"<DEFINITION-REF [^>]*>.*?</DEFINITION-REF>.*?"
    r"<PARAMETER-VALUES>.*?"
    r"<ECUC-NUMERICAL-PARAM-VALUE>.*?"
    r"<DEFINITION-REF [^>]*>.*?/NrFmy</DEFINITION-REF>.*?"
    r"<VALUE>(\d+)</VALUE>",
    re.DOTALL
)


def process_arxml(arxml_path: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Extracts a value from the given arxml file, validates it, and returns the value and its double.
    
    Calls `extract_value` on `arxml_path`, checks if the result is a digit, and if so returns 
    it as an integer along with its double; otherwise, returns (None, None).
    
    Args:
        arxml_path: Path to the ARXML file
        
    Returns:
        Tuple of (val, val*2) or (None, None) if not found/invalid
    """
    fmy = extract_value(arxml_path)
    if not fmy or not fmy[0].isdigit():
        logger.error("Extracted value not valid. Exiting.")
        return None, None
    val = int(fmy[0])
    return val, val * 2


def extract_value(filename: str) -> List[str]:
    """
    Extracts Fmy/NrFmy values from ARXML file using regex pattern.
    
    Args:
        filename: Path to the ARXML file
        
    Returns:
        List of extracted values
    """
    
    with open(filename, "r", encoding="utf-8") as f:
        results = _FMY_PATTERN.findall(f.read())
    
    if not results:
        logger.warning("The value of Fmy is not declared in file: %s", filename)
    
    return results
