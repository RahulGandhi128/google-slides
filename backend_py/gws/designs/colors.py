"""
Color resolution for design primitives: theme defaults + hex overrides.
"""
from __future__ import annotations


def hex_to_rgb_floats(hex_str: str | None) -> dict[str, float]:
    """Convert '#RRGGBB' -> {red, green, blue} floats 0..1 for Slides API rgbColor."""
    s = (hex_str or "").strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) != 6:
        return {"red": 0.0, "green": 0.0, "blue": 0.0}
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
        return {"red": r, "green": g, "blue": b}
    except ValueError:
        return {"red": 0.0, "green": 0.0, "blue": 0.0}


def resolve_colors(
    theme_colors: dict | None,
    override: list[str] | None,
    count: int,
    default_palette: list[str] | None = None,
) -> list[dict[str, float]]:
    """
    Resolve colors for design elements. Uses override if provided, else theme, else defaults.

    Args:
        theme_colors: Dict with accent_color, shapes_color, charts_color (hex strings)
        override: Optional list of hex strings for per-element colors
        count: Number of colors needed
        default_palette: Fallback hex colors if no theme/override (e.g. blue, green, orange)

    Returns:
        List of {red, green, blue} dicts for Slides API, length >= count.
    """
    if override and len(override) >= count:
        return [hex_to_rgb_floats(h) for h in override[:count]]

    if isinstance(theme_colors, dict):
        palette = [
            theme_colors.get("accent_color") or "#3366CC",
            theme_colors.get("shapes_color") or "#34A853",
            theme_colors.get("charts_color") or "#EA4335",
            theme_colors.get("heading_color") or "#333333",
        ]
    elif default_palette:
        palette = default_palette
    else:
        palette = ["#3366CC", "#34A853", "#EA4335", "#FBBC04", "#9E69AF"]

    result: list[dict[str, float]] = []
    for i in range(count):
        hex_val = palette[i % len(palette)]
        result.append(hex_to_rgb_floats(hex_val))
    return result
