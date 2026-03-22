"""
Branding logos stored in DB.

We store:
- original bytes (PNG) for archival/future use
- a small data URL (<= ~2KB) for Slides createImage embedding
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text

from .connection import engine


def upsert_logo(role: str, filename: str, content_type: str, png_bytes: bytes, small_data_url: str) -> dict[str, Any]:
    role = (role or "").strip().lower()
    if role not in ("my", "target"):
        raise ValueError("role must be 'my' or 'target'")
    if not small_data_url or not isinstance(small_data_url, str):
        raise ValueError("small_data_url required")
    now = datetime.utcnow().isoformat()
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO branding_logos (role, filename, content_type, png_bytes, small_data_url, logo_url, created_at, updated_at)
                VALUES (:role, :filename, :content_type, :png_bytes, :small_data_url, NULL, :now, :now)
                ON CONFLICT(role) DO UPDATE SET
                    filename = excluded.filename,
                    content_type = excluded.content_type,
                    png_bytes = excluded.png_bytes,
                    small_data_url = excluded.small_data_url,
                    logo_url = NULL,
                    updated_at = excluded.updated_at
                """
            ),
            {
                "role": role,
                "filename": filename or "",
                "content_type": content_type or "image/png",
                "png_bytes": png_bytes,
                "small_data_url": small_data_url,
                "now": now,
            },
        )
        conn.commit()
        row = conn.execute(
            text("SELECT id, role, filename, content_type, created_at, updated_at FROM branding_logos WHERE role = :role"),
            {"role": role},
        ).fetchone()
    return {
        "id": row[0],
        "role": row[1],
        "filename": row[2],
        "contentType": row[3],
        "createdAt": row[4],
        "updatedAt": row[5],
    }


def list_logos() -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, role, filename, content_type, small_data_url, logo_url, created_at, updated_at FROM branding_logos ORDER BY role ASC")
        ).fetchall()
    return [
        {
            "id": r[0],
            "role": r[1],
            "filename": r[2],
            "contentType": r[3],
            "smallDataUrl": r[4],
            "logoUrl": r[5],
            "createdAt": r[6],
            "updatedAt": r[7],
        }
        for r in rows
    ]


def get_small_data_url_by_role(role: str) -> str | None:
    role = (role or "").strip().lower()
    if role not in ("my", "target"):
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT small_data_url FROM branding_logos WHERE role = :role"),
            {"role": role},
        ).fetchone()
    return (row[0] if row else None) or None


def get_logo_image_url_by_role(role: str) -> str | None:
    """Return URL to use for scaffold: logo_url if set, else small_data_url."""
    role = (role or "").strip().lower()
    if role not in ("my", "target"):
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT logo_url, small_data_url FROM branding_logos WHERE role = :role"),
            {"role": role},
        ).fetchone()
    if not row:
        return None
    logo_url, small_data_url = row[0], row[1]
    if logo_url and isinstance(logo_url, str) and logo_url.strip():
        return logo_url.strip()
    return (small_data_url if small_data_url else None) or None


def get_logo_url_for_scaffold(role: str, base_url: str | None) -> str | None:
    """
    Return best URL for scaffold: logo_url if set, else base_url + /api/branding/logo/{role}/image
    when base_url is set and we have png_bytes, else small_data_url.
    Use base_url when running behind a tunnel (localtunnel/ngrok) so Google can fetch logos.
    """
    role = (role or "").strip().lower()
    if role not in ("my", "target"):
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT logo_url, small_data_url, png_bytes FROM branding_logos WHERE role = :role"),
            {"role": role},
        ).fetchone()
    if not row:
        return None
    logo_url, small_data_url, png_bytes = row[0], row[1], row[2]
    if logo_url and isinstance(logo_url, str) and logo_url.strip():
        return logo_url.strip()
    base = (base_url or "").strip().rstrip("/")
    if base and png_bytes and len(png_bytes) > 0:
        return f"{base}/api/branding/logo/{role}/image"
    return (small_data_url if small_data_url else None) or None


def get_logo_png_bytes(role: str) -> bytes | None:
    """Return raw PNG bytes for logo (for serving via HTTP)."""
    role = (role or "").strip().lower()
    if role not in ("my", "target"):
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT png_bytes FROM branding_logos WHERE role = :role"),
            {"role": role},
        ).fetchone()
    if not row or not row[0]:
        return None
    return row[0]


def upsert_logo_url(role: str, url: str) -> dict[str, Any]:
    """Store a public logo URL for the role (no upload). Use for createImage in scaffold."""
    role = (role or "").strip().lower()
    if role not in ("my", "target"):
        raise ValueError("role must be 'my' or 'target'")
    url = (url or "").strip()
    if not url:
        raise ValueError("url required")
    if not url.startswith(("http://", "https://")):
        raise ValueError("url must start with http:// or https://")
    now = datetime.utcnow().isoformat()
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO branding_logos (role, filename, content_type, png_bytes, small_data_url, logo_url, created_at, updated_at)
                VALUES (:role, '', 'url', NULL, NULL, :logo_url, :now, :now)
                ON CONFLICT(role) DO UPDATE SET
                    logo_url = excluded.logo_url,
                    updated_at = excluded.updated_at
                """
            ),
            {"role": role, "logo_url": url, "now": now},
        )
        conn.commit()
        row = conn.execute(
            text("SELECT id, role, filename, content_type, created_at, updated_at FROM branding_logos WHERE role = :role"),
            {"role": role},
        ).fetchone()
    return {
        "id": row[0],
        "role": row[1],
        "filename": row[2],
        "contentType": row[3],
        "createdAt": row[4],
        "updatedAt": row[5],
    }


def upsert_logo_prefs(
    my_corner: str | None,
    target_corner: str | None,
    my_width_emu: int | None = None,
    my_height_emu: int | None = None,
    my_margin_emu: int | None = None,
    target_width_emu: int | None = None,
    target_height_emu: int | None = None,
    target_margin_emu: int | None = None,
) -> None:
    """
    Save corner preferences (global single-row).
    Corners: top_left, top_right, bottom_left, bottom_right.
    """
    def _norm(c: str | None) -> str | None:
        c = (c or "").strip().lower()
        if not c:
            return None
        if c not in ("top_left", "top_right", "bottom_left", "bottom_right"):
            raise ValueError("corner must be one of top_left, top_right, bottom_left, bottom_right")
        return c

    my_c = _norm(my_corner)
    tgt_c = _norm(target_corner)
    now = datetime.utcnow().isoformat()

    def _norm_int(v: Any) -> int | None:
        if v is None or v == "":
            return None
        try:
            i = int(v)
        except Exception:
            return None
        return i if i > 0 else None

    my_w = _norm_int(my_width_emu)
    my_h = _norm_int(my_height_emu)
    my_m = _norm_int(my_margin_emu)
    tgt_w = _norm_int(target_width_emu)
    tgt_h = _norm_int(target_height_emu)
    tgt_m = _norm_int(target_margin_emu)

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO branding_logo_prefs (
                    id,
                    my_corner, target_corner,
                    my_width_emu, my_height_emu, my_margin_emu,
                    target_width_emu, target_height_emu, target_margin_emu,
                    updated_at
                )
                VALUES (
                    1,
                    :my_corner, :target_corner,
                    :my_width_emu, :my_height_emu, :my_margin_emu,
                    :target_width_emu, :target_height_emu, :target_margin_emu,
                    :now
                )
                ON CONFLICT(id) DO UPDATE SET
                    my_corner = excluded.my_corner,
                    target_corner = excluded.target_corner,
                    my_width_emu = excluded.my_width_emu,
                    my_height_emu = excluded.my_height_emu,
                    my_margin_emu = excluded.my_margin_emu,
                    target_width_emu = excluded.target_width_emu,
                    target_height_emu = excluded.target_height_emu,
                    target_margin_emu = excluded.target_margin_emu,
                    updated_at = excluded.updated_at
                """
            ),
            {
                "my_corner": my_c,
                "target_corner": tgt_c,
                "my_width_emu": my_w,
                "my_height_emu": my_h,
                "my_margin_emu": my_m,
                "target_width_emu": tgt_w,
                "target_height_emu": tgt_h,
                "target_margin_emu": tgt_m,
                "now": now,
            },
        )
        conn.commit()


def get_logo_prefs() -> dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT my_corner, target_corner, my_width_emu, my_height_emu, my_margin_emu, "
                "target_width_emu, target_height_emu, target_margin_emu, updated_at "
                "FROM branding_logo_prefs WHERE id = 1"
            )
        ).fetchone()
    if not row:
        return {"myCorner": None, "targetCorner": None}
    return {
        "myCorner": row[0],
        "targetCorner": row[1],
        "myWidthEmu": row[2],
        "myHeightEmu": row[3],
        "myMarginEmu": row[4],
        "targetWidthEmu": row[5],
        "targetHeightEmu": row[6],
        "targetMarginEmu": row[7],
        "updatedAt": row[8],
    }

