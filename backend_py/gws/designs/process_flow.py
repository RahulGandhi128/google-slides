"""
Process flow infographic: boxes connected by arrows (horizontal or vertical).
Returns batch update requests. Use grouping to keep the design as one moveable unit.
"""
from __future__ import annotations

from .base import EMU, SLIDE_W, SLIDE_H
from .colors import resolve_colors


def generate_requests(
    page_object_id: str,
    steps: list[str],
    *,
    orientation: str = "horizontal",
    translate_x: int | None = None,
    translate_y: int | None = None,
    theme_colors: dict | None = None,
    colors: list[str] | None = None,
    id_prefix: str = "process",
    box_width_emu: int | None = None,
    box_height_emu: int | None = None,
    arrow_size_emu: int | None = None,
) -> list[dict]:
    """
    Generate batch update requests for a process flow infographic.

    Args:
        page_object_id: Slide's page object ID
        steps: Labels for each step (e.g. ["Research", "Build", "Launch"])
        orientation: "horizontal" or "vertical"
        translate_x: Left/top anchor in EMU (default: centered)
        translate_y: Top anchor in EMU (default: ~1/3 from top)
        theme_colors: Theme dict with accent_color, shapes_color, etc. (hex)
        colors: Override - list of hex strings per step
        id_prefix: Prefix for object IDs
        box_width_emu: Box width (default ~1.5 in)
        box_height_emu: Box height (default ~1 in)
        arrow_size_emu: Arrow size (default ~0.4 in)

    Returns:
        List of batch update request dicts (createShape, updateShapeProperties, insertText, groupObjects)
    """
    requests: list[dict] = []

    if not steps:
        return requests

    box_w = int((box_width_emu or 1.5 * EMU))
    box_h = int(box_height_emu or 1.0 * EMU)
    arrow_sz = int(arrow_size_emu or 0.4 * EMU)

    rgb_list = resolve_colors(theme_colors, colors, len(steps))

    # Default position: centered horizontally, ~1/3 from top
    horiz = orientation.lower() in ("horizontal", "h")
    step_span = (box_w + arrow_sz) if horiz else (box_h + arrow_sz)
    total_w = len(steps) * box_w + (len(steps) - 1) * arrow_sz if horiz else box_w
    total_h = box_h if horiz else len(steps) * box_h + (len(steps) - 1) * arrow_sz

    start_x = translate_x if translate_x is not None else (SLIDE_W - total_w) // 2
    start_y = translate_y if translate_y is not None else int(SLIDE_H * 0.2)

    child_ids: list[str] = []

    for i, step_text in enumerate(steps):
        if horiz:
            x = start_x + i * (box_w + arrow_sz)
            y = start_y
        else:
            x = start_x
            y = start_y + i * (box_h + arrow_sz)

        box_id = f"{id_prefix}_box_{i}"
        arrow_id = f"{id_prefix}_arrow_{i}"

        # Create box (ROUND_RECTANGLE)
        requests.append({
            "createShape": {
                "objectId": box_id,
                "shapeType": "ROUND_RECTANGLE",
                "elementProperties": {
                    "pageObjectId": page_object_id,
                    "size": {
                        "width": {"magnitude": box_w, "unit": "EMU"},
                        "height": {"magnitude": box_h, "unit": "EMU"},
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
        child_ids.append(box_id)

        # Fill color
        requests.append({
            "updateShapeProperties": {
                "objectId": box_id,
                "fields": "shapeBackgroundFill.solidFill.color",
                "shapeProperties": {
                    "shapeBackgroundFill": {
                        "solidFill": {"color": {"rgbColor": rgb_list[i]}}
                    }
                },
            }
        })

        # Label text
        requests.append({
            "insertText": {
                "objectId": box_id,
                "text": step_text,
                "insertionIndex": 0,
            }
        })

        # Arrow between boxes (skip after last)
        if i < len(steps) - 1:
            if horiz:
                arrow_x = x + box_w
                arrow_y = y + int(0.3 * EMU)
                aw, ah = arrow_sz, int(0.4 * EMU)
                arrow_type = "RIGHT_ARROW"
            else:
                arrow_x = x + int(0.3 * EMU)
                arrow_y = y + box_h
                aw, ah = int(0.4 * EMU), arrow_sz
                arrow_type = "DOWN_ARROW"

            requests.append({
                "createShape": {
                    "objectId": arrow_id,
                    "shapeType": arrow_type,
                    "elementProperties": {
                        "pageObjectId": page_object_id,
                        "size": {
                            "width": {"magnitude": aw, "unit": "EMU"},
                            "height": {"magnitude": ah, "unit": "EMU"},
                        },
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": arrow_x,
                            "translateY": arrow_y,
                            "unit": "EMU",
                        },
                    },
                }
            })
            child_ids.append(arrow_id)

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
