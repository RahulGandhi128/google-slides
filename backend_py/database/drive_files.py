"""Drive files storage - sync from gws to SQLite."""
from datetime import datetime

from sqlalchemy import text

from .connection import engine


def upsert_drive_files(files: list[dict]) -> None:
    """Upsert files from gws response into drive_files table."""
    if not files:
        return
    now = datetime.utcnow().isoformat()
    with engine.connect() as conn:
        for f in files:
            fid = f.get("id")
            if not fid:
                continue
            conn.execute(
                text("""
                INSERT INTO drive_files (id, name, mime_type, modified_time, web_view_link, icon_link, synced_at)
                VALUES (:id, :name, :mime_type, :modified_time, :web_view_link, :icon_link, :synced_at)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    mime_type = excluded.mime_type,
                    modified_time = excluded.modified_time,
                    web_view_link = excluded.web_view_link,
                    icon_link = excluded.icon_link,
                    synced_at = excluded.synced_at
                """),
                {
                    "id": fid,
                    "name": f.get("name", ""),
                    "mime_type": f.get("mimeType"),
                    "modified_time": f.get("modifiedTime"),
                    "web_view_link": f.get("webViewLink"),
                    "icon_link": f.get("iconLink"),
                    "synced_at": now,
                },
            )
        conn.commit()


def get_drive_files_from_db() -> list[dict]:
    """Return files from DB in API format."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
            SELECT id, name, mime_type, modified_time, web_view_link, icon_link
            FROM drive_files ORDER BY modified_time DESC
            """)
        ).fetchall()
    return [
        {
            "id": r[0],
            "name": r[1],
            "mimeType": r[2],
            "modifiedTime": r[3],
            "webViewLink": r[4],
            "iconLink": r[5],
        }
        for r in rows
    ]
