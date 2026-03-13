"""
Documents: metadata and ingestion.
Every ingested file is chunked and indexed with FAISS (no page/size limit).
Stores: documents row (metadata) + document_indexes (FAISS blobs).
"""
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text

from database.connection import engine

logger = logging.getLogger(__name__)

# Import pipeline from file path to avoid package init / wrong module
def _datapipeline():
    import importlib.util
    _here = Path(__file__).resolve().parent
    _pipe_path = _here.parent / "functions" / "datapipeline.py"
    if not _pipe_path.exists():
        raise ImportError(f"datapipeline.py not found at {_pipe_path}")
    spec = importlib.util.spec_from_file_location("datapipeline", _pipe_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return (
        getattr(mod, "extract_text_with_metadata"),
        getattr(mod, "chunk_document"),
    )


def _document_search():
    from functions.document_search import build_index_from_chunks, save_index_to_db
    return build_index_from_chunks, save_index_to_db


def ingest_document(file_path: str | os.PathLike, filename: str | None = None) -> dict[str, Any]:
    """
    Ingest a .pdf or .docx file: extract text, chunk, build FAISS index, save to DB.
    Uses original filename when provided (e.g. from upload); otherwise path.name.
    Returns {upload_id, filename, page_count, has_faiss: True}. No page/size limit; every file is indexed.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in (".pdf", ".docx"):
        raise ValueError("Only .pdf and .docx are supported.")

    display_name = (filename or path.name).strip() or path.name

    extract_text_with_metadata, chunk_document = _datapipeline()
    meta = extract_text_with_metadata(path)
    text_content = meta["text"]
    page_count = meta.get("page_count", 0)
    pages = meta.get("pages", [])

    if not (text_content or "").strip():
        raise ValueError("Document produced no text.")

    chunks = chunk_document(
        text_content,
        page_count=page_count,
        pages=pages if pages else None,
        format="pdf" if suffix == ".pdf" else "docx",
    )
    if not chunks:
        raise ValueError("Document produced no chunks.")

    build_index_from_chunks, save_index_to_db = _document_search()
    vectorstore = build_index_from_chunks(chunks)
    upload_id = str(uuid.uuid4())
    save_index_to_db(upload_id, vectorstore)

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO documents (upload_id, filename, page_count, full_text, has_faiss)
                VALUES (:upload_id, :filename, :page_count, NULL, 1)
            """),
            {
                "upload_id": upload_id,
                "filename": display_name,
                "page_count": page_count,
            },
        )
        conn.commit()

    logger.info("Ingested document upload_id=%s filename=%s chunks=%d", upload_id, display_name, len(chunks))
    return {"upload_id": upload_id, "filename": display_name, "page_count": page_count, "has_faiss": True}


def list_documents(limit: int = 100) -> list[dict[str, Any]]:
    """List ingested documents, most recent first."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT upload_id, filename, page_count, has_faiss, created_at
                FROM documents ORDER BY created_at DESC LIMIT :limit
            """),
            {"limit": limit},
        ).fetchall()
    return [
        {
            "upload_id": r[0],
            "filename": r[1],
            "page_count": r[2],
            "has_faiss": bool(r[3]),
            "created_at": r[4],
        }
        for r in rows
    ]


def get_document_text(upload_id: str) -> str | None:
    """Return full text for a small document. For FAISS docs, returns None (use search_document)."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT full_text, has_faiss FROM documents WHERE upload_id = :id"),
            {"id": upload_id},
        ).fetchone()
    if not row:
        return None
    full_text, has_faiss = row[0], row[1]
    if has_faiss:
        return None  # caller should use document_search
    return full_text or ""
