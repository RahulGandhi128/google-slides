"""
Slide templates: named slide outlines with guidance.
Stored as one row per template with slides JSON.
"""
import json
from datetime import datetime
from typing import Any

from sqlalchemy import text

from .connection import engine


def list_templates(limit: int = 100) -> list[dict[str, Any]]:
  """List saved slide templates, most recent first."""
  with engine.connect() as conn:
      rows = conn.execute(
          text(
              """
              SELECT id, name, slides_json, created_at, updated_at
              FROM slide_templates
              ORDER BY updated_at DESC
              LIMIT :limit
              """
          ),
          {"limit": limit},
      ).fetchall()
  templates: list[dict[str, Any]] = []
  for r in rows:
      slides: list[dict[str, Any]] = []
      try:
          raw = r[2] or "[]"
          slides = json.loads(raw)
          if not isinstance(slides, list):
              slides = []
      except Exception:
          slides = []
      templates.append(
          {
              "id": r[0],
              "name": r[1],
              "slides": slides,
              "createdAt": r[3],
              "updatedAt": r[4],
          }
      )
  return templates


def upsert_template(name: str, slides: list[dict[str, Any]]) -> None:
  """
  Insert or update a slide template by name.
  Uses SQLite ON CONFLICT for simplicity.
  """
  name = (name or "").strip()
  if not name:
      raise ValueError("Template name must not be empty")

  safe_slides: list[dict[str, Any]] = []
  for s in slides or []:
      if not isinstance(s, dict):
          continue
      safe_slides.append(
          {
              "title": (s.get("title") or "").strip(),
              "guidance": (s.get("guidance") or "").strip(),
          }
      )
  slides_json = json.dumps(safe_slides, ensure_ascii=False)
  now = datetime.utcnow().isoformat()

  with engine.connect() as conn:
      conn.execute(
          text(
              """
              INSERT INTO slide_templates (name, slides_json, created_at, updated_at)
              VALUES (:name, :slides, :now, :now)
              ON CONFLICT(name) DO UPDATE SET
                  slides_json = excluded.slides_json,
                  updated_at = excluded.updated_at
              """
          ),
          {"name": name, "slides": slides_json, "now": now},
      )
      conn.commit()


def delete_template(template_id: int) -> bool:
    """Delete a slide template by id. Returns True if deleted."""
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM slide_templates WHERE id = :id"),
            {"id": template_id},
        )
        conn.commit()
        return result.rowcount > 0

