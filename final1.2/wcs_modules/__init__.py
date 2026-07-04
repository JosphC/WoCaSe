"""
WCS Test Configuration Tool - Modular Version

This package contains the modularized components of the WCS tool.

Modules:
    - main: Main application orchestrator
    - qt_ui: Modern PyQt6 user interface
    - templates: File templates (XML, GRL, CBD, C)
    - file_generator: File creation logic
    - arxml_processor: ARXML parsing and processing
    - gpt_detector: GPT function detection in headers
    - code_modifier: C source code modification
    - xml_modifier: XML/CBD file modification
    - tdcl_modifier: TDCL file modification
    - path_utils: Path and directory utilities
    - td5_builder: TD5 build system integration
    - simulator_bridge: Integration bridge to DEM MainFunction Runtime Simulator

Usage:
    from wcs_modules.qt_ui import launch_qt_app
"""

__version__ = "2.2.0"
__author__ = "Al-Yafeai Yosif"

# TD5 Build Configuration Constants
TD5_PATH = r"C:\LegacyApp\TD5\4.4.0\eclipse_cli\td5.exe"
BUILD_TYPE = "NORMAL"
BUILD_RULE = "All"

__all__ = [
    'launch_qt_app',
    'TD5_PATH',
    'BUILD_TYPE',
    'BUILD_RULE',
    'logging_config',
    'simulator_bridge',
]

# Import Qt application launcher for convenience
from .qt_ui import launch_qt_app
