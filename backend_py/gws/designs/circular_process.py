"""
Circular process infographic: steps arranged on a circle with optional arrows.
Returns batch update requests. Uses grouping to keep the design as one unit.
"""
from __future__ import annotations

import math

from .base import EMU, SLIDE_W, SLIDE_H
from .colors import hex_to_rgb_floats, resolve_colors


def generate_requests(
    page_object_id: str,
    steps: list[str],
    *,
    arrow_count: int | None = None,
    radius_emu: int | None = None,
    start_angle_deg: float = 0,
    center_x: int | None = None,
    center_y: int | None = None,
    theme_colors: dict | None = None,
    colors: list[str] | None = None,
    id_prefix: str = "circular",
    node_width_emu: int | None = None,
    node_height_emu: int | None = None,
) -> list[dict]:
    """
    Generate batch update requests for a circular process infographic.

    Args:
        page_object_id: Slide's page object ID
        steps: Labels for each step (e.g. ["Phase 1", "Phase 2", "Phase 3", "Phase 4"])
        arrow_count: Number of arrows between steps (default: len(steps)). Use 0 to omit arrows.
        radius_emu: Radius of the circle in EMU (default ~2.2 in)
        start_angle_deg: Start angle in degrees (0=right, 90=bottom, clockwise)
        center_x: Center X in EMU (default: slide center)
        center_y: Center Y in EMU (default: slide center)
        theme_colors: Theme dict for default colors
        colors: Override - list of hex strings per step
        id_prefix: Prefix for object IDs
        node_width_emu: Node box width (default ~1.2 in)
        node_height_emu: Node box height (default ~0.8 in)

    Returns:
        List of batch update request dicts (createShape, updateShapeProperties, insertText, groupObjects)
    """
    requests: list[dict] = []

    if not steps:
        return requests

    n = len(steps)
    cx = center_x if center_x is not None else SLIDE_W // 2
    cy = center_y if center_y is not None else SLIDE_H // 2
    radius = int(radius_emu or 2.2 * EMU)
    node_w = int(node_width_emu or 1.2 * EMU)
    node_h = int(node_height_emu or 0.8 * EMU)
    num_arrows = arrow_count if arrow_count is not None else n
    num_arrows = max(0, min(num_arrows, n))

    rgb_list = resolve_colors(theme_colors, colors, n)

    # Angle step (clockwise from start)
    step_deg = 360.0 / n if n > 0 else 0
    start_rad = math.radians(start_angle_deg)

    child_ids: list[str] = []
    text_pad_x = int(0.08 * EMU)
    text_pad_y = int(0.06 * EMU)

    for i, step_text in enumerate(steps):
        angle_rad = start_rad + math.radians(i * step_deg)
        # Position node center on circle
        nx = cx + radius * math.cos(angle_rad)
        ny = cy + radius * math.sin(angle_rad)
        # Top-left for element (element origin is top-left)
        x = int(nx - node_w / 2)
        y = int(ny - node_h / 2)
        node_id = f"{id_prefix}_node_{i}"
        text_id = f"{id_prefix}_node_text_{i}"

        # Create node (ROUND_RECTANGLE)
        requests.append({
            "createShape": {
                "objectId": node_id,
                "shapeType": "ROUND_RECTANGLE",
                "elementProperties": {
                    "pageObjectId": page_object_id,
                    "size": {
                        "width": {"magnitude": node_w, "unit": "EMU"},
                        "height": {"magnitude": node_h, "unit": "EMU"},
                    },
                    "transform": {
                        "scaleX": 1,
                        "scaleY": 1,
                        "translateX": x,
                        "translateY": y,
                        "unit": "EMU",
                    },
                },
            }
        })
        child_ids.append(node_id)

        # Fill color
        requests.append({
            "updateShapeProperties": {
                "objectId": node_id,
                "fields": "shapeBackgroundFill.solidFill.color",
                "shapeProperties": {
                    "shapeBackgroundFill": {
                        "solidFill": {"color": {"rgbColor": rgb_list[i]}}
                    }
                },
            }
        })

        # Inner text box (prebuilt text container inside the node)
        text_w = max(int(0.35 * EMU), node_w - (2 * text_pad_x))
        text_h = max(int(0.20 * EMU), node_h - (2 * text_pad_y))
        requests.append({
            "createShape": {
                "objectId": text_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": page_object_id,
                    "size": {
                        "width": {"magnitude": text_w, "unit": "EMU"},
                        "height": {"magnitude": text_h, "unit": "EMU"},
                    },
                    "transform": {
                        "scaleX": 1,
                        "scaleY": 1,
                        "translateX": x + text_pad_x,
                        "translateY": y + text_pad_y,
                        "unit": "EMU",
                    },
                },
            }
        })
        child_ids.append(text_id)

        # Label text
        requests.append({
            "insertText": {
                "objectId": text_id,
                "text": step_text,
                "insertionIndex": 0,
            }
        })

    # Arrows between consecutive nodes (clockwise)
    arrow_sz = int(0.35 * EMU)
    arrow_accent = theme_colors.get("accent_color") or "#3366CC" if isinstance(theme_colors, dict) else "#3366CC"
    arrow_rgb = hex_to_rgb_floats(arrow_accent)

    for i in range(num_arrows):
        j = (i + 1) % n
        # Midpoint between node i and node j
        angle_i = start_rad + math.radians(i * step_deg)
        angle_j = start_rad + math.radians(j * step_deg)
        mx = cx + (radius - 0.3 * EMU) * math.cos((angle_i + angle_j) / 2)
        my = cy + (radius - 0.3 * EMU) * math.sin((angle_i + angle_j) / 2)

        # Arrow direction: from i toward j
        dx = math.cos(angle_j) - math.cos(angle_i)
        dy = math.sin(angle_j) - math.sin(angle_i)
        angle_arrow = math.atan2(dy, dx)  # radians, 0 = right

        # Transform for rotation: scaleX=cos, scaleY=cos, shearX=sin, shearY=-sin
        cos_a = math.cos(angle_arrow)
        sin_a = math.sin(angle_arrow)
        # Position: top-left of arrow (arrow points right by default, size arrow_sz x arrow_sz)
        ax = int(mx - arrow_sz / 2)
        ay = int(my - arrow_sz / 2)
        arrow_id = f"{id_prefix}_arrow_{i}"

        requests.append({
            "createShape": {
                "objectId": arrow_id,
                "shapeType": "RIGHT_ARROW",
                "elementProperties": {
                    "pageObjectId": page_object_id,
                    "size": {
                        "width": {"magnitude": arrow_sz, "unit": "EMU"},
                        "height": {"magnitude": arrow_sz, "unit": "EMU"},
                    },
                    "transform": {
                        "scaleX": cos_a,
                        "scaleY": cos_a,
                        "shearX": sin_a,
                        "shearY": -sin_a,
                        "translateX": ax,
                        "translateY": ay,
                        "unit": "EMU",
                    },
                },
            }
        })
        child_ids.append(arrow_id)

        # Arrow fill
        requests.append({
            "updateShapeProperties": {
                "objectId": arrow_id,
                "fields": "shapeBackgroundFill.solidFill.color",
                "shapeProperties": {
                    "shapeBackgroundFill": {
                        "solidFill": {"color": {"rgbColor": arrow_rgb}}
                    }
                },
            }
        })

    # Group all elements
    if len(child_ids) >= 2:
        group_id = f"{id_prefix}_group"
        requests.append({
            "groupObjects": {
                "childrenObjectIds": child_ids,
                "groupObjectId": group_id,
            }
        })

    return requests
