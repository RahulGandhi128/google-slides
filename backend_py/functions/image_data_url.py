"""
Deterministically shrink PNG bytes to a small data URL (<~2KB).

This is used for embedding logos directly in Slides createImage(url=...).
When URL length exceeds ~2000 chars, Slides API requests may fail.
"""

from __future__ import annotations

import base64
from io import BytesIO


def make_small_png_data_url(png_bytes: bytes, max_url_len: int = 2000, return_best_len: bool = False):
    """
    Downsize + quantize PNG until data URL length <= max_url_len.
    Returns data URL string or None if cannot be shrunk enough.
    """
    if not png_bytes:
        return (None, None) if return_best_len else None

    try:
        from PIL import Image
    except ImportError:
        b64 = base64.b64encode(png_bytes).decode("ascii")
        data_url = f"data:image/png;base64,{b64}"
        if len(data_url) <= max_url_len:
            return (data_url, len(data_url)) if return_best_len else data_url
        return (None, len(data_url)) if return_best_len else None

    # Start small; logos are typically placed small on slides anyway.
    # We try a range of increasingly aggressive options; some logos are complex.
    size_candidates = [96, 72, 64, 56, 48, 40, 32, 24, 20, 16, 12, 10, 8, 6, 4]
    color_candidates = [64, 32, 16, 8, 4, 2]
    best_len = None
    best_url = None

    for s in size_candidates:
        for colors in color_candidates:
            try:
                img = Image.open(BytesIO(png_bytes)).convert("RGBA")
                # Flatten transparency onto white to improve compression
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                bg.alpha_composite(img)
                img = bg.convert("RGB")
                img.thumbnail((s, s), Image.LANCZOS)
                img_q = img.quantize(colors=colors, method=Image.MEDIANCUT)
                buf = BytesIO()
                img_q.save(buf, format="PNG", optimize=True, compress_level=9)
                out = buf.getvalue()
            except Exception:
                continue

            b64 = base64.b64encode(out).decode("ascii")
            data_url = f"data:image/png;base64,{b64}"
            l = len(data_url)
            if best_len is None or l < best_len:
                best_len = l
                best_url = data_url
            if l <= max_url_len:
                return (data_url, l) if return_best_len else data_url

    return (None, best_len) if return_best_len else None

