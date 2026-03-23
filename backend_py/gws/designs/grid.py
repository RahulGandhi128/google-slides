"""
Grid infographic: stat cards with top panel (stat, heading, body) and
bottom panel (arrow + bullet list). Theme-aware colors throughout.
Uses grouping to keep the design as one moveable unit.
"""
from __future__ import annotations

from .base import EMU, SLIDE_W, SLIDE_H
from .colors import hex_to_rgb_floats, resolve_colors


# ── request helpers ──────────────────────────────────────────────────────────

def _create_shape(obj_id, page_id, x, y, w, h, shape="RECTANGLE"):
    return {"createShape": {
        "objectId": obj_id,
        "shapeType": shape,
        "elementProperties": {
            "pageObjectId": page_id,
            "size": {
                "width":  {"magnitude": w, "unit": "EMU"},
                "height": {"magnitude": h, "unit": "EMU"},
            },
            "transform": {
                "scaleX": 1, "scaleY": 1,
                "translateX": x, "translateY": y,
                "unit": "EMU",
            },
        },
    }}


def _fill(obj_id, rgb):
    return {"updateShapeProperties": {
        "objectId": obj_id,
        "fields": "shapeBackgroundFill.solidFill.color",
        "shapeProperties": {
            "shapeBackgroundFill": {
                "solidFill": {"color": {"rgbColor": rgb}}
            }
        },
    }}


def _outline(obj_id, rgb, pt=1.5):
    return {"updateShapeProperties": {
        "objectId": obj_id,
        "fields": "outline",
        "shapeProperties": {
            "outline": {
                "outlineFill": {"solidFill": {"color": {"rgbColor": rgb}}},
                "weight": {"magnitude": pt, "unit": "PT"},
                "dashStyle": "SOLID",
            }
        },
    }}


def _no_outline(obj_id):
    return {"updateShapeProperties": {
        "objectId": obj_id,
        "fields": "outline.propertyState",
        "shapeProperties": {
            "outline": {
                "propertyState": "NOT_RENDERED",
            }
        },
    }}


def _insert_text(obj_id, text, idx=0):
    return {"insertText": {"objectId": obj_id, "text": text, "insertionIndex": idx}}


def _text_style(obj_id, rgb, pt, bold=False):
    return {
        "updateTextStyle": {
            "objectId": obj_id,
            "style": {
                "foregroundColor": {"opaqueColor": {"rgbColor": rgb}},
                "fontSize": {"magnitude": pt, "unit": "PT"},
                "bold": bold,
            },
            "fields": "foregroundColor,fontSize,bold",
        }
    }


def _para_align(obj_id, alignment="START"):
    return {"updateParagraphStyle": {
        "objectId": obj_id,
        "style": {"alignment": alignment},
        "fields": "alignment",
    }}


def _darken(rgb: dict, factor: float = 0.78) -> dict:
    """Slightly darken an RGB dict for borders/outlines."""
    return {
        "red": round(rgb.get("red", 0) * factor, 4),
        "green": round(rgb.get("green", 0) * factor, 4),
        "blue": round(rgb.get("blue", 0) * factor, 4),
    }


_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
_DARK_TEXT = {"red": 0.2, "green": 0.2, "blue": 0.2}


# ── main ─────────────────────────────────────────────────────────────────────

def generate_requests(
    page_object_id: str,
    rows: int = 1,
    columns: int = 3,
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
    Generate batch update requests for a stat-card grid infographic.

    Each card contains:
      - Top white panel: stat box (big number), bold heading, body paragraph
      - Bottom accent panel: down arrow + bullet list

    Colors are derived from theme_colors or the colors override. Each card
    gets a unique accent from the palette.

    Args:
        page_object_id: Slide's page object ID
        rows: Ignored (cards are always a single visual row)
        columns: Number of cards (default 3)
        cells: Optional list of card data. Each item is a string (becomes stat)
               or dict with keys: stat, heading, body, bullets.
        translate_x: Left anchor in EMU (default: centered)
        translate_y: Top anchor in EMU (default: ~10% from top)
        theme_colors: Dict with accent_color, shapes_color, charts_color, heading_color, body_text_color (hex)
        colors: Override - list of hex strings, one per card
        id_prefix: Prefix for object IDs
        cell_width_emu: Card width (default auto-fits slide)
        cell_height_emu: Card height (default ~4.8 in)
        gap_emu: Gap between cards (default ~0.15 in)
    """
    requests: list[dict] = []

    n_cards = max(1, columns)

    # ── sizing ────────────────────────────────────────────────────────────────
    gap = int(gap_emu or 0.15 * EMU)
    margin = int(0.5 * EMU)

    if cell_width_emu:
        card_w = int(cell_width_emu)
    else:
        card_w = (SLIDE_W - 2 * margin - (n_cards - 1) * gap) // n_cards

    card_h = int(cell_height_emu or 4.8 * EMU)

    top_h = int(card_h * 0.58)
    bot_h = card_h - top_h

    stat_box_w = int(card_w * 0.60)
    stat_box_h = int(top_h * 0.24)

    pad_x = int(0.15 * EMU)
    pad_y = int(0.12 * EMU)

    total_w = n_cards * card_w + (n_cards - 1) * gap
    start_x = translate_x if translate_x is not None else (SLIDE_W - total_w) // 2
    start_y = translate_y if translate_y is not None else int(SLIDE_H * 0.10)

    # ── resolve accent colors from theme or override ─────────────────────────
    accent_rgb_list = resolve_colors(theme_colors, colors, n_cards)

    # Text colors from theme or sensible defaults
    heading_text_rgb = _DARK_TEXT
    body_text_rgb = _DARK_TEXT
    if isinstance(theme_colors, dict):
        if theme_colors.get("heading_color"):
            heading_text_rgb = hex_to_rgb_floats(theme_colors["heading_color"])
        if theme_colors.get("body_text_color"):
            body_text_rgb = hex_to_rgb_floats(theme_colors["body_text_color"])

    # ── default cell data ─────────────────────────────────────────────────────
    _defaults = {
        "stat": "—",
        "heading": "Heading",
        "body": "Description text goes here.",
        "bullets": ["Item 1", "Item 2", "Item 3"],
    }

    card_data: list[dict] = []
    for i in range(n_cards):
        base = dict(_defaults)
        base["stat"] = f"#{i + 1}"
        if cells and i < len(cells):
            item = cells[i]
            if isinstance(item, dict):
                base.update({k: v for k, v in item.items() if v})
            elif isinstance(item, str):
                base["stat"] = item
        card_data.append(base)

    all_child_ids: list[str] = []

    for ci, data in enumerate(card_data):
        px = start_x + ci * (card_w + gap)
        py = start_y

        accent = accent_rgb_list[ci]
        accent_dark = _darken(accent)

        stat_text = data.get("stat", f"#{ci + 1}")
        heading_text = data.get("heading", "Heading")
        body_text = data.get("body", "")
        bullets = data.get("bullets", [])

        # 1. White top panel
        top_id = f"{id_prefix}_c{ci}_top"
        requests += [
            _create_shape(top_id, page_object_id, px, py, card_w, top_h),
            _fill(top_id, _WHITE),
            _outline(top_id, accent_dark, pt=1.0),
        ]
        all_child_ids.append(top_id)

        # 2. Stat box (accent-outlined rect with big number/%)
        sb_x = px + pad_x
        sb_y = py + pad_y
        sb_id = f"{id_prefix}_c{ci}_stat"
        requests += [
            _create_shape(sb_id, page_object_id, sb_x, sb_y, stat_box_w, stat_box_h),
            _fill(sb_id, _WHITE),
            _outline(sb_id, accent_dark, pt=1.5),
            _insert_text(sb_id, stat_text),
            _text_style(sb_id, accent, pt=36, bold=True),
            _para_align(sb_id, "CENTER"),
        ]
        all_child_ids.append(sb_id)

        # 3. Heading text box
        hd_x = px + pad_x
        hd_y = sb_y + stat_box_h + int(0.10 * EMU)
        hd_w = card_w - 2 * pad_x
        hd_h = int(top_h * 0.20)
        hd_id = f"{id_prefix}_c{ci}_heading"
        requests += [
            _create_shape(hd_id, page_object_id, hd_x, hd_y, hd_w, hd_h, "TEXT_BOX"),
            _no_outline(hd_id),
            _insert_text(hd_id, heading_text),
            _text_style(hd_id, accent, pt=14, bold=True),
        ]
        all_child_ids.append(hd_id)

        # 4. Body paragraph text box
        bp_x = px + pad_x
        bp_y = hd_y + hd_h + int(0.06 * EMU)
        bp_w = card_w - 2 * pad_x
        bp_h = int(top_h * 0.34)
        bp_id = f"{id_prefix}_c{ci}_body"
        requests += [
            _create_shape(bp_id, page_object_id, bp_x, bp_y, bp_w, bp_h, "TEXT_BOX"),
            _no_outline(bp_id),
            _insert_text(bp_id, body_text),
            _text_style(bp_id, body_text_rgb, pt=9),
        ]
        all_child_ids.append(bp_id)

        # 5. Bottom accent panel
        bot_y = py + top_h
        bot_id = f"{id_prefix}_c{ci}_bot"
        requests += [
            _create_shape(bot_id, page_object_id, px, bot_y, card_w, bot_h),
            _fill(bot_id, accent),
            _outline(bot_id, accent_dark, pt=1.0),
        ]
        all_child_ids.append(bot_id)

        # 6. Down-arrow shape
        arr_w = int(0.32 * EMU)
        arr_h = int(0.20 * EMU)
        arr_x = px + (card_w - arr_w) // 2
        arr_y = bot_y + int(0.10 * EMU)
        arr_id = f"{id_prefix}_c{ci}_arrow"
        requests += [
            _create_shape(arr_id, page_object_id, arr_x, arr_y, arr_w, arr_h, "DOWN_ARROW"),
            _fill(arr_id, _WHITE),
            _no_outline(arr_id),
        ]
        all_child_ids.append(arr_id)

        # 7. Bullet list text box
        bl_x = px + pad_x
        bl_y = arr_y + arr_h + int(0.06 * EMU)
        bl_w = card_w - 2 * pad_x
        bl_h = max(int(0.5 * EMU), bot_h - (bl_y - bot_y) - int(0.08 * EMU))
        bl_id = f"{id_prefix}_c{ci}_bullets"

        bullet_text = "\n".join(f"• {b}" for b in bullets) if bullets else ""
        requests += [
            _create_shape(bl_id, page_object_id, bl_x, bl_y, bl_w, bl_h, "TEXT_BOX"),
            _no_outline(bl_id),
            _insert_text(bl_id, bullet_text),
            _text_style(bl_id, _WHITE, pt=9),
        ]
        all_child_ids.append(bl_id)

    # Group everything
    if len(all_child_ids) >= 2:
        requests.append({
            "groupObjects": {
                "childrenObjectIds": all_child_ids,
                "groupObjectId": f"{id_prefix}_group",
            }
        })

    return requests
