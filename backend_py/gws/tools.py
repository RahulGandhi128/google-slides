"""
Google Slides & Drive tools - gws CLI wrappers
"""
from .executor import run_gws


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
