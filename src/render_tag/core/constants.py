"""
Core constants for render-tag.

This module contains static data like tag family specifications,
isolated from logic to prevent non-deterministic import cycles.
"""

# Bit counts for each tag family (used for minimum pixel area calculation)
TAG_BIT_COUNTS = {
    "tag36h11": 36,
    "tag36h10": 36,
    "tag25h9": 25,
    "tag16h5": 16,
    "tagCircle21h7": 21,
    "tagCircle49h12": 49,
    "tagCustom48h12": 48,
    "tagStandard41h12": 41,
    "tagStandard52h13": 52,
    "DICT_4X4_50": 16,
    "DICT_4X4_100": 16,
    "DICT_4X4_250": 16,
    "DICT_6X6_1000": 36,
    "DICT_7X7_50": 49,
    "DICT_7X7_100": 49,
    "DICT_7X7_250": 49,
    "DICT_7X7_1000": 49,
    "DICT_ARUCO_ORIGINAL": 25,
}

# Grid dimensions (total bits across) for each tag family
# This is data_bits + 2 (for the black border)
TAG_GRID_SIZES = {
    "tag36h11": 8,
    "tag36h10": 8,
    "tag25h9": 7,
    "tag16h5": 6,
    "tagCircle21h7": 9,  # Approximate for circle tags
    "tagCircle49h12": 11,
    "tagCustom48h12": 10,
    "tagStandard41h12": 9,
    "tagStandard52h13": 10,
    "DICT_4X4_50": 6,
    "DICT_4X4_100": 6,
    "DICT_4X4_250": 6,
    "DICT_6X6_1000": 8,
    "DICT_7X7_50": 9,
    "DICT_7X7_100": 9,
    "DICT_7X7_250": 9,
    "DICT_7X7_1000": 9,
    "DICT_ARUCO_ORIGINAL": 7,  # 5x5 data
}

# Schema Versioning
CURRENT_SCHEMA_VERSION = "0.2"
