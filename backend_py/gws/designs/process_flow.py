"""
Process flow infographic: overlapping chevron headers + body panels below.
Theme-aware colors throughout. Uses grouping to keep the design as one unit.
"""
from __future__ import annotations

from .base import EMU, SLIDE_W, SLIDE_H
from .colors import hex_to_rgb_floats, resolve_colors


# ── request helpers ──────────────────────────────────────────────────────────

def _create_shape(obj_id, page_id, shape_type, x, y, w, h):
    return {"createShape": {
        "objectId": obj_id,
        "shapeType": shape_type,
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
            "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb}}}
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
            "outline": {"propertyState": "NOT_RENDERED"}
        },
    }}


def _insert_text(obj_id, text, idx=0):
    return {"insertText": {"objectId": obj_id, "text": text, "insertionIndex": idx}}


def _text_style(obj_id, rgb, pt, bold=False):
    return {"updateTextStyle": {
        "objectId": obj_id,
        "style": {
            "foregroundColor": {"opaqueColor": {"rgbColor": rgb}},
            "fontSize": {"magnitude": pt, "unit": "PT"},
            "bold": bold,
        },
        "fields": "foregroundColor,fontSize,bold",
    }}


def _para_align(obj_id, alignment="CENTER"):
    return {"updateParagraphStyle": {
        "objectId": obj_id,
        "style": {"alignment": alignment},
        "fields": "alignment",
    }}


def _darken(rgb: dict, factor: float = 0.70) -> dict:
    return {
        "red": round(rgb.get("red", 0) * factor, 4),
        "green": round(rgb.get("green", 0) * factor, 4),
        "blue": round(rgb.get("blue", 0) * factor, 4),
    }


def _lighten(rgb: dict, factor: float = 0.25) -> dict:
    """Mix rgb towards white by factor (0 = unchanged, 1 = white)."""
    return {
        "red": round(rgb.get("red", 0) + (1.0 - rgb.get("red", 0)) * factor, 4),
        "green": round(rgb.get("green", 0) + (1.0 - rgb.get("green", 0)) * factor, 4),
        "blue": round(rgb.get("blue", 0) + (1.0 - rgb.get("blue", 0)) * factor, 4),
    }


_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
_DARK_TEXT = {"red": 0.196, "green": 0.196, "blue": 0.196}
_PANEL_BORDER = hex_to_rgb_floats("#ADC6E1")  # light blue (matches reference design)


# ── main ─────────────────────────────────────────────────────────────────────

def generate_requests(
    page_object_id: str,
    steps: list[str | dict],
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
    Generate batch update requests for a chevron process-flow infographic.

    Layout per step:
      - PENTAGON chevron header (overlapping, coloured) with white label
      - White rectangle below with accent-coloured border, body paragraph

    Colors are derived from theme_colors or the colors override. Each step
    gets a unique accent from the palette, producing a gradient effect.

    Args:
        page_object_id: Slide page ID
        steps: List of step data. Each item is a plain string (becomes the
               chevron label with default body text), or a dict with keys
               "label" and "body".
        orientation: Ignored (always horizontal); kept for backward compat.
        translate_x: Left anchor in EMU (default: centered)
        translate_y: Top anchor in EMU (default: ~10% from top)
        theme_colors: Dict with accent_color, shapes_color, charts_color,
                      heading_color, body_text_color (hex strings)
        colors: Override — list of hex strings, one per step
        id_prefix: Object-ID prefix
        box_width_emu: Width of each chevron+panel unit (default auto-fits)
        box_height_emu: Height of the chevron header (default ~0.65 in)
        arrow_size_emu: Horizontal overlap of chevrons (default ~0.28 in)
    """
    requests: list[dict] = []
    if not steps:
        return requests

    n = len(steps)

    # ── sizing ────────────────────────────────────────────────────────────────
    # RIGHT_ARROW "joins" look best with slightly smaller overlap than before,
    # otherwise the arrow heads/tails visibly collide.
    overlap = int(arrow_size_emu or 0.20 * EMU)
    chev_h = int(box_height_emu or 0.65 * EMU)
    margin = int(0.4 * EMU)

    if box_width_emu:
        chev_w = int(box_width_emu)
    else:
        total_available = SLIDE_W - 2 * margin
        chev_w = (total_available + (n - 1) * overlap) // n

    panel_h = int(3.0 * EMU)
    gap_y = int(0.06 * EMU)

    step_x = chev_w - overlap
    total_w = step_x * n + overlap

    start_x = translate_x if translate_x is not None else (SLIDE_W - total_w) // 2
    start_y = translate_y if translate_y is not None else int(SLIDE_H * 0.10)
    panel_y = start_y + chev_h + gap_y

    # ── resolve accent colors from theme or override ─────────────────────────
    accent_rgb_list = resolve_colors(theme_colors, colors, n)

    body_text_rgb = _DARK_TEXT
    if isinstance(theme_colors, dict) and theme_colors.get("body_text_color"):
        body_text_rgb = hex_to_rgb_floats(theme_colors["body_text_color"])

    # ── parse steps ───────────────────────────────────────────────────────────
    parsed: list[tuple[str, str]] = []
    default_body = "Description text goes here."
    for s in steps:
        if isinstance(s, dict):
            parsed.append((s.get("label", "Step"), s.get("body", default_body)))
        else:
            parsed.append((str(s), default_body))

    all_ids: list[str] = []

    # ── draw body panels first (so chevrons layer on top) ─────────────────────
    for i, (label, body) in enumerate(parsed):
        panel_x = start_x + i * step_x
        panel_w = step_x if i < n - 1 else chev_w

        accent = accent_rgb_list[i]

        panel_id = f"{id_prefix}_panel_{i}"
        tb_id = f"{id_prefix}_panel_text_{i}"

        pad_x = int(0.12 * EMU)
        pad_y = int(0.12 * EMU)

        requests += [
            _create_shape(panel_id, page_object_id, "RECTANGLE",
                          panel_x, panel_y, panel_w, panel_h),
            _fill(panel_id, _WHITE),
            # Remove the outer outline to eliminate the “blue border around
            # text boxes” look.
            _no_outline(panel_id),
        ]
        all_ids.append(panel_id)

        tb_w = panel_w - 2 * pad_x
        tb_h = panel_h - 2 * pad_y
        requests += [
            _create_shape(tb_id, page_object_id, "TEXT_BOX",
                          panel_x + pad_x, panel_y + pad_y, tb_w, tb_h),
            _no_outline(tb_id),
            _insert_text(tb_id, body),
            _text_style(tb_id, body_text_rgb, pt=10),
            _para_align(tb_id, "START"),
        ]
        all_ids.append(tb_id)

    # ── draw chevrons on top ──────────────────────────────────────────────────
    for i, (label, _) in enumerate(parsed):
        chev_x = start_x + i * step_x
        chev_id = f"{id_prefix}_chev_{i}"
        lbl_id = f"{id_prefix}_chev_lbl_{i}"

        accent = accent_rgb_list[i]

        requests += [
            _create_shape(chev_id, page_object_id, "RIGHT_ARROW",
                          chev_x, start_y, chev_w, chev_h),
            _fill(chev_id, accent),
            _no_outline(chev_id),
        ]
        all_ids.append(chev_id)

        lbl_pad_x = int(0.10 * EMU)
        lbl_pad_y = int(0.08 * EMU)
        lbl_w = chev_w - 2 * lbl_pad_x
        lbl_h = chev_h - 2 * lbl_pad_y
        requests += [
            _create_shape(lbl_id, page_object_id, "TEXT_BOX",
                          chev_x + lbl_pad_x, start_y + lbl_pad_y, lbl_w, lbl_h),
            _no_outline(lbl_id),
            _insert_text(lbl_id, label),
            _text_style(lbl_id, _WHITE, pt=16, bold=True),
            _para_align(lbl_id, "CENTER"),
        ]
        all_ids.append(lbl_id)

    # ── group everything ──────────────────────────────────────────────────────
    if len(all_ids) >= 2:
        requests.append({
            "groupObjects": {
                "childrenObjectIds": all_ids,
                "groupObjectId": f"{id_prefix}_group",
            }
        })

    return requests
