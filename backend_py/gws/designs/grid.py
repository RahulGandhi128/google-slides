"""
Grid infographic: rows × columns of cells (stat cards, data grid, etc.).
Returns batch update requests. Uses grouping to keep the design as one unit.
"""
from __future__ import annotations

from .base import EMU, SLIDE_W, SLIDE_H
from .colors import hex_to_rgb_floats, resolve_colors


def generate_requests(
    page_object_id: str,
    rows: int,
    columns: int,
    cells: list[str | dict] | None = None,
    *,
    translate_x: int | None = None,
    translate_y: int | None = None,
    theme_colors: dict | None = None,
    colors: list[str] | None = None,
    id_prefix: str = "grid",
    cell_width_emu: int | None = None,
    cell_height_emu: int | None = None,
    gap_emu: int | None = None,
) -> list[dict]:
    """
    Generate batch update requests for a grid infographic.

    Args:
        page_object_id: Slide's page object ID
        rows: Number of rows
        columns: Number of columns
        cells: Optional list of cell content. Each item is a string or {"text": "...", "color": "#hex"}.
               If shorter than rows*columns, remaining cells get placeholder text.
        translate_x: Left anchor in EMU (default: centered)
        translate_y: Top anchor in EMU (default: ~1/5 from top)
        theme_colors: Theme dict for default colors
        colors: Override - flat list of hex strings (row-major order)
        id_prefix: Prefix for object IDs
        cell_width_emu: Cell width (default ~2 in)
        cell_height_emu: Cell height (default ~1 in)
        gap_emu: Gap between cells (default ~0.2 in)

    Returns:
        List of batch update request dicts (createShape, updateShapeProperties, insertText, groupObjects)
    """
    requests: list[dict] = []

    total_cells = rows * columns
    if total_cells <= 0:
        return requests

    cell_w = int(cell_width_emu or 2.0 * EMU)
    cell_h = int(cell_height_emu or 1.0 * EMU)
    gap = int(gap_emu or 0.2 * EMU)

    # Parse cells: support strings or {"text": "...", "color": "#hex"}
    parsed: list[tuple[str, str | None]] = []
    for i in range(total_cells):
        if cells and i < len(cells):
            item = cells[i]
            if isinstance(item, dict):
                parsed.append((item.get("text", ""), item.get("color")))
            else:
                parsed.append((str(item), None))
        else:
            parsed.append((f"Cell {i + 1}", None))

    # Resolve colors: per-cell from parsed, else flat colors override, else theme
    default_rgb = resolve_colors(theme_colors, colors, total_cells)
    rgb_list: list[dict] = []
    for i, (_, cell_hex) in enumerate(parsed):
        if cell_hex:
            rgb_list.append(hex_to_rgb_floats(cell_hex))
        else:
            rgb_list.append(default_rgb[i])

    # Total size
    total_w = columns * cell_w + (columns - 1) * gap
    total_h = rows * cell_h + (rows - 1) * gap

    start_x = translate_x if translate_x is not None else (SLIDE_W - total_w) // 2
    start_y = translate_y if translate_y is not None else int(SLIDE_H * 0.15)

    child_ids: list[str] = []

    for idx in range(total_cells):
        r = idx // columns
        c = idx % columns
        x = start_x + c * (cell_w + gap)
        y = start_y + r * (cell_h + gap)
        cell_id = f"{id_prefix}_cell_{idx}"
        text, _ = parsed[idx]

        # Create cell (ROUND_RECTANGLE)
        requests.append({
            "createShape": {
                "objectId": cell_id,
                "shapeType": "ROUND_RECTANGLE",
                "elementProperties": {
                    "pageObjectId": page_object_id,
                    "size": {
                        "width": {"magnitude": cell_w, "unit": "EMU"},
                        "height": {"magnitude": cell_h, "unit": "EMU"},
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
        child_ids.append(cell_id)

        # Fill color
        requests.append({
            "updateShapeProperties": {
                "objectId": cell_id,
                "fields": "shapeBackgroundFill.solidFill.color",
                "shapeProperties": {
                    "shapeBackgroundFill": {
                        "solidFill": {"color": {"rgbColor": rgb_list[idx]}}
                    }
                },
            }
        })

        # Cell text
        requests.append({
            "insertText": {
                "objectId": cell_id,
                "text": text,
                "insertionIndex": 0,
            }
        })

    # Group all cells
    if len(child_ids) >= 2:
        group_id = f"{id_prefix}_group"
        requests.append({
            "groupObjects": {
                "childrenObjectIds": child_ids,
                "groupObjectId": group_id,
            }
        })

    return requests
