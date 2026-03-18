"""
Google Slides & Drive tools - gws CLI wrappers
"""
from .executor import run_gws


def _hex_to_rgb_floats(hex_str: str) -> dict:
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


def _make_color_scheme(theme_colors: dict | None) -> dict | None:
    """
    Build a Slides ColorScheme payload for updatePageProperties.pageProperties.colorScheme.
    Slides API expects rgb floats, not hex strings.
    """
    if not isinstance(theme_colors, dict) or not theme_colors:
        return None

    bg = theme_colors.get("background_color") or "#FFFFFF"
    text = theme_colors.get("body_text_color") or "#111111"
    heading = theme_colors.get("heading_color") or text
    accent = theme_colors.get("accent_color") or heading
    shapes = theme_colors.get("shapes_color") or accent
    charts = theme_colors.get("charts_color") or shapes

    # Slides color schemes are keyed by ThemeColorType and must appear in a stable order.
    # We map our logical theme_colors to a minimal, coherent scheme.
    ordered_types = [
        "DARK1",
        "LIGHT1",
        "DARK2",
        "LIGHT2",
        "ACCENT1",
        "ACCENT2",
        "ACCENT3",
        "ACCENT4",
        "ACCENT5",
        "ACCENT6",
        "HYPERLINK",
        "FOLLOWED_HYPERLINK",
        "TEXT1",
        "BACKGROUND1",
        "TEXT2",
        "BACKGROUND2",
    ]

    # Pick reasonable assignments. DARK/LIGHT are the base text/background pair.
    mapping = {
        "DARK1": text,
        "LIGHT1": bg,
        "DARK2": heading,
        "LIGHT2": bg,
        "ACCENT1": accent,
        "ACCENT2": shapes,
        "ACCENT3": charts,
        "ACCENT4": accent,
        "ACCENT5": shapes,
        "ACCENT6": charts,
        "HYPERLINK": accent,
        "FOLLOWED_HYPERLINK": charts,
        "TEXT1": text,
        "BACKGROUND1": bg,
        "TEXT2": heading,
        "BACKGROUND2": bg,
    }

    return {
        "colors": [
            {"type": t, "color": _hex_to_rgb_floats(mapping[t])}
            for t in ordered_types
        ]
    }


def presentations_create(title: str = "Untitled Presentation") -> dict:
    """Create a new Google Slides presentation."""
    r = run_gws(["slides", "presentations", "create"], json_body={"title": title})
    if isinstance(r, dict) and r.get("presentationId"):
        r["presentationUrl"] = f"https://docs.google.com/presentation/d/{r['presentationId']}/edit"
    return r


def presentations_get(presentation_id: str) -> dict:
    """Get full content of a presentation."""
    return run_gws(["slides", "presentations", "get"], params={"presentationId": presentation_id})


def presentations_batch_update(presentation_id: str, requests: list[dict]) -> dict:
    """Apply batch updates (create slides, insert text, etc.)."""
    return run_gws(
        ["slides", "presentations", "batchUpdate"],
        params={"presentationId": presentation_id},
        json_body={"requests": requests},
    )


def pages_get_thumbnail(presentation_id: str, page_object_id: str) -> dict:
    """Get thumbnail for a slide."""
    return run_gws(
        ["slides", "pages", "getThumbnail"],
        params={"presentationId": presentation_id, "pageObjectId": page_object_id},
    )


def drive_files_list(
    page_size: int = 30,
    q: str | None = None,
    fields: str | None = "files(id,name,mimeType,modifiedTime,webViewLink,iconLink)",
) -> dict:
    """List files in Google Drive. Returns {files: [...], nextPageToken?: ...}."""
    params = {"pageSize": page_size}
    if q:
        params["q"] = q
    if fields:
        params["fields"] = fields
    return run_gws(["drive", "files", "list"], params=params)


def scaffold_presentation(
    title: str,
    num_slides: int,
    theme_colors: dict | None = None,
    logo_url: str | None = None,
    logos: list[dict] | None = None,
) -> dict:
    """
    Create a new presentation with a global theme color scheme + N slides scaffolded.
    - Updates master color scheme (Theme Builder-like) via updatePageProperties.colorScheme on the master.
    - Creates (num_slides - 1) slides with stable placeholderIdMappings (TITLE/BODY).
    - Applies background fill to each slide and optionally adds the logo image to each slide.
    Returns {presentationId, presentationUrl, slides:[{pageObjectId,titleObjectId,bodyObjectId}], masterObjectId?}
    """
    num_slides = int(num_slides or 0)
    if num_slides <= 0:
        raise ValueError("num_slides must be >= 1")

    created = presentations_create(title=title or "Untitled Presentation")
    if not isinstance(created, dict) or not created.get("presentationId"):
        raise RuntimeError("Failed to create presentation")
    presentation_id = created["presentationId"]

    pres = presentations_get(presentation_id)
    if not isinstance(pres, dict):
        raise RuntimeError("Failed to fetch presentation after create")

    # First slide already exists (Google creates one default slide).
    slides_arr = pres.get("slides") or []
    if not slides_arr:
        raise RuntimeError("Presentation has no slides")
    first_slide_obj = slides_arr[0]
    first_slide_id = first_slide_obj.get("objectId") or first_slide_obj.get("pageObjectId")
    if not first_slide_id:
        raise RuntimeError("Could not determine first slide objectId")

    # Find a master objectId for true Theme Builder-like color scheme updates.
    masters = pres.get("masters") or []
    master_id = None
    if masters and isinstance(masters, list) and isinstance(masters[0], dict):
        master_id = masters[0].get("objectId")

    requests: list[dict] = []

    def _batch_update_chunks(reqs: list[dict], chunk_size: int) -> None:
        """Send batchUpdate in smaller chunks to avoid Windows command-line length limits."""
        if not reqs:
            return
        chunk_size = int(chunk_size or 0)
        if chunk_size <= 0:
            chunk_size = 25
        for i in range(0, len(reqs), chunk_size):
            presentations_batch_update(presentation_id, reqs[i : i + chunk_size])

    # 1) Update the master color scheme (global theme colors).
    scheme = _make_color_scheme(theme_colors)
    if master_id and scheme:
        requests.append(
            {
                "updatePageProperties": {
                    "objectId": master_id,
                    "pageProperties": {"colorScheme": scheme},
                    "fields": "colorScheme.colors",
                }
            }
        )

    # 2) Create truly blank slides (no layout placeholders).
    # We'll create slide_1..slide_N with predefinedLayout BLANK, then remove the auto-created slide.
    scaffold = []
    create_reqs = []
    for idx in range(1, num_slides + 1):
        slide_id = f"slide_{idx}"
        create_reqs.append(
            {
                "createSlide": {
                    "objectId": slide_id,
                    "insertionIndex": idx - 1,
                    "slideLayoutReference": {"predefinedLayout": "BLANK"},
                }
            }
        )
        scaffold.append({"pageObjectId": slide_id, "titleObjectId": None, "bodyObjectId": None})

    # Execute: master scheme (small) + create slides (chunked)
    _batch_update_chunks(requests, chunk_size=10)
    _batch_update_chunks(create_reqs, chunk_size=25)

    # Remove the default slide so the deck contains only our blank scaffold slides.
    _batch_update_chunks([{"deleteObject": {"objectId": first_slide_id}}], chunk_size=1)

    # 3) Apply background color per slide (helps even if master scheme isn't applied everywhere).
    bg_hex = None
    if isinstance(theme_colors, dict):
        bg_hex = theme_colors.get("background_color")
    if bg_hex:
        rgb = _hex_to_rgb_floats(bg_hex)
        bg_reqs = []
        for s in scaffold:
            bg_reqs.append(
                {
                    "updatePageProperties": {
                        "objectId": s["pageObjectId"],
                        "pageProperties": {
                            "pageBackgroundFill": {
                                "solidFill": {"color": {"rgbColor": rgb}}
                            }
                        },
                        "fields": "pageBackgroundFill",
                    }
                }
            )
        _batch_update_chunks(bg_reqs, chunk_size=25)

    # 4) Add logo image(s) to every slide if provided.
    # Slide size in EMU (16:9): width≈9144000, height≈6858000.
    SLIDE_W = 9144000
    SLIDE_H = 6858000

    def _corner_xy(corner: str, w: int, h: int, margin: int) -> tuple[int, int]:
        corner = (corner or "top_right").strip().lower()
        if corner == "top_left":
            return margin, margin
        if corner == "top_right":
            return SLIDE_W - w - margin, margin
        if corner == "bottom_left":
            return margin, SLIDE_H - h - margin
        if corner == "bottom_right":
            return SLIDE_W - w - margin, SLIDE_H - h - margin
        # default
        return SLIDE_W - w - margin, margin

    logo_items: list[dict] = []
    # Backward compat: single logo_url -> one logo at top-right
    if logo_url:
        logo_items.append({"url": logo_url, "corner": "top_right", "idPrefix": "logo"})
    if isinstance(logos, list):
        for it in logos:
            if isinstance(it, dict) and it.get("url"):
                logo_items.append(it)

    if logo_items:
        # Logos can make payloads large; send in small chunks. Also split per-logo to keep chunks small.
        for it in logo_items:
            url = it.get("url")
            corner = it.get("corner") or "top_right"
            w = int(it.get("widthEmu") or 600000)
            h = int(it.get("heightEmu") or 600000)
            margin = int(it.get("marginEmu") or 250000)
            prefix = (it.get("idPrefix") or "logo").strip() or "logo"
            tx, ty = _corner_xy(corner, w, h, margin)
            logo_reqs = []
            for i, s in enumerate(scaffold, start=1):
                logo_reqs.append(
                    {
                        "createImage": {
                            "objectId": f"{prefix}_{i}",
                            "url": url,
                            "elementProperties": {
                                "pageObjectId": s["pageObjectId"],
                                "size": {
                                    "width": {"magnitude": w, "unit": "EMU"},
                                    "height": {"magnitude": h, "unit": "EMU"},
                                },
                                "transform": {
                                    "scaleX": 1,
                                    "scaleY": 1,
                                    "translateX": int(tx),
                                    "translateY": int(ty),
                                    "unit": "EMU",
                                },
                            },
                        }
                    }
                )
            _batch_update_chunks(logo_reqs, chunk_size=10)

    return {
        "presentationId": presentation_id,
        "presentationUrl": created.get("presentationUrl"),
        "masterObjectId": master_id,
        "slides": scaffold,
    }
