"""
Timeline infographic: horizontal green bar with alternating above/below events.
Each event has:
  - A filled circle dot on the timeline
  - A year label at the line
  - A text card (bold heading + body) above or below
Returns batch update requests grouped as one unit.
"""
from __future__ import annotations

from .base import EMU, SLIDE_W, SLIDE_H
from .colors import hex_to_rgb_floats, resolve_colors


# ── colour helpers ────────────────────────────────────────────────────────────
def _rgb(r, g, b):
    return {"red": round(r / 255, 4), "green": round(g / 255, 4), "blue": round(b / 255, 4)}


def _hex(h: str):
    h = h.lstrip("#")
    return _rgb(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


_BLACK      = _rgb(20,  20, 20)
_TEXT_DARK  = _rgb(50,  50, 50)
_WHITE      = _rgb(255, 255, 255)


# ── request builders ──────────────────────────────────────────────────────────
def _shape(obj_id, page_id, shape_type, x, y, w, h):
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


def _no_border(obj_id):
    return {"updateShapeProperties": {
        "objectId": obj_id,
        # Use NOT_RENDERED to avoid Slides API rejecting outline weight <= 0.
        "fields": "outline.propertyState",
        "shapeProperties": {"outline": {"propertyState": "NOT_RENDERED"}},
    }}


def _text(obj_id, content, idx=0):
    return {"insertText": {"objectId": obj_id, "text": content, "insertionIndex": idx}}


def _style(obj_id, rgb, pt, bold=False, start: int | None = None, end: int | None = None):
    req = {"updateTextStyle": {
        "objectId": obj_id,
        "style": {
            "foregroundColor": {"opaqueColor": {"rgbColor": rgb}},
            "fontSize": {"magnitude": pt, "unit": "PT"},
            "bold": bold,
        },
        "fields": "foregroundColor,fontSize,bold",
    }}
    if start is not None or end is not None:
        tr: dict = {}
        # When both provided, use a fixed range so Slides accepts endIndex.
        if start is not None and end is not None:
            tr["type"] = "FIXED_RANGE"
        if start is not None:
            tr["startIndex"] = start
        if end is not None:
            tr["endIndex"] = end
        req["updateTextStyle"]["textRange"] = tr
    return req


def _align(obj_id, alignment="START"):
    return {"updateParagraphStyle": {
        "objectId": obj_id,
        "style": {"alignment": alignment},
        "fields": "alignment",
    }}


def _darken(rgb: dict, factor: float = 0.72) -> dict:
    return {
        "red": round(rgb.get("red", 0) * factor, 4),
        "green": round(rgb.get("green", 0) * factor, 4),
        "blue": round(rgb.get("blue", 0) * factor, 4),
    }


# ── main ──────────────────────────────────────────────────────────────────────
def generate_requests(
    page_object_id: str,
    events: list[str | dict],
    *,
    translate_x: int | None = None,
    translate_y: int | None = None,
    theme_colors: dict | None = None,
    colors: list[str] | None = None,
    id_prefix: str = "timeline",
    total_width_emu: int | None = None,
    bar_height_emu: int | None = None,
) -> list[dict]:
    """
    Generate batch update requests for a horizontal alternating timeline.

    Each event alternates above/below the green timeline bar:
      - Odd  index (0, 2, …) → dot + year above bar, text card above
      - Even index (1, 3, …) → dot + year below bar, text card below

    Args:
        page_object_id  : Slide page ID.
        events          : List of event dicts or plain year strings.
                          Dict keys:
                            "year"    – label shown at the timeline dot  (default "20XX")
                            "heading" – bold title in the card            (default placeholder)
                            "body"    – paragraph text in the card        (default placeholder)
        translate_x/y   : Top-left of the whole timeline in EMU.
        theme_colors    : Theme palette dict (hex values) – used for bar/dot color.
        colors          : Per-event hex overrides (not used in this layout, kept for compat).
        id_prefix       : Object-ID prefix.
        total_width_emu : Full width of the green bar (default: ~9.2 in).
        bar_height_emu  : Thickness of the timeline bar (default ~0.13 in).

    Returns:
        List of Google Slides API batchUpdate request dicts.
    """
    requests: list[dict] = []
    if not events:
        return requests

    n = len(events)

    # ── sizing ────────────────────────────────────────────────────────────────
    BAR_W     = int(total_width_emu or 9.2 * EMU)
    BAR_H     = int(bar_height_emu  or 0.13 * EMU)

    DOT_D     = int(0.18 * EMU)          # dot diameter
    STEM_H    = int(0.28 * EMU)          # vertical line from dot to bar
    YEAR_H    = int(0.30 * EMU)          # height of year label box
    YEAR_W    = int(0.80 * EMU)

    CARD_W    = int(1.90 * EMU)          # text card width
    CARD_H    = int(1.50 * EMU)          # text card height
    CARD_GAP  = int(0.08 * EMU)          # gap between year label and card

    # Vertical centre of the bar on the slide
    START_X   = translate_x if translate_x is not None else (SLIDE_W - BAR_W) // 2
    BAR_CY    = (translate_y if translate_y is not None else int(SLIDE_H * 0.50))
    BAR_Y     = BAR_CY - BAR_H // 2

    # Evenly space events along the bar
    if n == 1:
        x_positions = [START_X + BAR_W // 2]
    else:
        spacing = BAR_W // (n - 1) if n > 1 else BAR_W
        x_positions = [START_X + i * spacing for i in range(n)]

    # ── colors (theme-aware) ────────────────────────────────────────────────
    accent_rgb_list = resolve_colors(
        theme_colors,
        colors,
        n,
        default_palette=["#00823C", "#16A34A", "#059669", "#047857"],
    )
    bar_rgb = accent_rgb_list[0]

    year_rgb = _BLACK
    card_heading_rgb = _BLACK
    card_body_rgb = _TEXT_DARK
    if isinstance(theme_colors, dict):
        if theme_colors.get("heading_color"):
            year_rgb = hex_to_rgb_floats(theme_colors["heading_color"])
            card_heading_rgb = year_rgb
        if theme_colors.get("body_text_color"):
            card_body_rgb = hex_to_rgb_floats(theme_colors["body_text_color"])

    # ── default content ───────────────────────────────────────────────────────
    _DEF_HEADING = "Vestibulum congue tempus"
    _DEF_BODY    = (
        "Lorem ipsum dolor sit amet, consectetur\n"
        "adipiscing elit, sed do eiusmod tempor.\n"
        "Donec facilisis lacus eget mauris."
    )

    parsed: list[dict] = []
    for e in events:
        if isinstance(e, dict):
            parsed.append({
                "year":    e.get("year",    "20XX"),
                "heading": e.get("heading", _DEF_HEADING),
                "body":    e.get("body",    _DEF_BODY),
            })
        else:
            parsed.append({"year": str(e), "heading": _DEF_HEADING, "body": _DEF_BODY})

    all_ids: list[str] = []

    # ── 1. Green timeline bar ─────────────────────────────────────────────────
    bar_id = f"{id_prefix}_bar"
    requests += [
        _shape(bar_id, page_object_id, "RECTANGLE",
               START_X, BAR_Y, BAR_W, BAR_H),
        _fill(bar_id, bar_rgb),
        _no_border(bar_id),
    ]
    all_ids.append(bar_id)

    # ── 2. Events ─────────────────────────────────────────────────────────────
    for i, data in enumerate(parsed):
        cx   = x_positions[i]          # centre x of this event
        above = (i % 2 == 0)           # True → content goes above the bar

        dot_x = cx - DOT_D // 2
        dot_y = BAR_Y + BAR_H // 2 - DOT_D // 2

        # ── dot ───────────────────────────────────────────────────────────────
        dot_id = f"{id_prefix}_dot_{i}"
        dot_rgb = _darken(accent_rgb_list[i], 0.78)
        requests += [
            _shape(dot_id, page_object_id, "ELLIPSE",
                   dot_x, dot_y, DOT_D, DOT_D),
            _fill(dot_id, dot_rgb),
            _no_border(dot_id),
        ]
        all_ids.append(dot_id)

        # ── year label ────────────────────────────────────────────────────────
        # Year sits just above or just below the bar
        yr_x = cx - YEAR_W // 2
        if above:
            yr_y = BAR_Y - YEAR_H - int(0.03 * EMU)   # just above bar
        else:
            yr_y = BAR_Y + BAR_H + int(0.03 * EMU)    # just below bar

        yr_id = f"{id_prefix}_year_{i}"
        requests += [
            _shape(yr_id, page_object_id, "TEXT_BOX",
                   yr_x, yr_y, YEAR_W, YEAR_H),
            _no_border(yr_id),
            _text(yr_id, data["year"]),
            _style(yr_id, year_rgb, pt=14, bold=True),
            _align(yr_id, "CENTER"),
        ]
        all_ids.append(yr_id)

        # ── text card (heading + body) ─────────────────────────────────────────
        card_x = cx - CARD_W // 2

        if above:
            # card sits above the year label
            card_y = yr_y - CARD_GAP - CARD_H
        else:
            # card sits below the year label
            card_y = yr_y + YEAR_H + CARD_GAP

        card_id = f"{id_prefix}_card_{i}"
        heading = data["heading"]
        body    = data["body"]
        full_text = heading + "\n" + body
        heading_end = len(heading)

        requests += [
            _shape(card_id, page_object_id, "TEXT_BOX",
                   card_x, card_y, CARD_W, CARD_H),
            _no_border(card_id),
            _text(card_id, full_text),
            # Bold heading
            _style(card_id, card_heading_rgb, pt=10, bold=True,  start=0, end=heading_end),
            # Normal body
            _style(card_id, card_body_rgb, pt=9, bold=False,
                   start=heading_end + 1, end=len(full_text)),
            _align(card_id, "START"),
        ]
        all_ids.append(card_id)

    # ── group everything ──────────────────────────────────────────────────────
    if len(all_ids) >= 2:
        requests.append({
            "groupObjects": {
                "childrenObjectIds": all_ids,
                "groupObjectId": f"{id_prefix}_group",
            }
        })

    return requests