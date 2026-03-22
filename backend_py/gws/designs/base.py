"""
Base utilities for design primitives (infographics, grids, etc.).
"""
from __future__ import annotations

from .colors import hex_to_rgb_floats, resolve_colors

__all__ = [
    "EMU",
    "SLIDE_W",
    "SLIDE_H",
    "hex_to_rgb_floats",
    "resolve_colors",
]

# 1 inch = 914,400 EMU (Slides API standard)
EMU = 914400

# Default 16:9 slide dimensions in EMU
SLIDE_W = 9_144_000
SLIDE_H = 6_858_000
