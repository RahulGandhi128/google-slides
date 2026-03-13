"""
document_search.py

Build and query FAISS vector indexes over uploaded document chunks.
Indexes are stored in the database (document_indexes table).

- build_index_from_chunks(chunks) -> FAISS vectorstore
- save_index_to_db(upload_id, vectorstore)  uses project DB
- load_index_from_db(upload_id) -> FAISS
- search_document(upload_id, query, k) -> list of chunk texts

Embeddings: DOCUMENT_EMBEDDING_MODEL / EMBEDDING_MODEL / ICON_EMBEDDING_MODEL.
API key: GOOGLE_GENERATIVE_AI_API_KEY or GEMINI_API_KEY.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from sqlalchemy import text

load_dotenv()

# Use project database
try:
    from database.connection import engine
except ImportError:
    engine = None

logger = logging.getLogger(__name__)

_EMBED_MODEL = (
    os.getenv("DOCUMENT_EMBEDDING_MODEL")
    or os.getenv("EMBEDDING_MODEL")
    or os.getenv("ICON_EMBEDDING_MODEL")
    or "models/gemini-embedding-001"
)


def _api_key() -> str:
    return (
        os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or ""
    )


def _make_embeddings() -> GoogleGenerativeAIEmbeddings:
    key = _api_key()
    if not key:
        raise ValueError(
            "Set GOOGLE_GENERATIVE_AI_API_KEY or GEMINI_API_KEY for document embeddings."
        )
    return GoogleGenerativeAIEmbeddings(
        model=_EMBED_MODEL,
        google_api_key=key,
    )


def build_index_from_chunks(chunks: list[dict[str, Any]]) -> FAISS:
    """Build a FAISS index from chunk dicts with 'content' and optional 'page'."""
    if not chunks:
        raise ValueError("Cannot build index from empty chunks.")
    docs = []
    for c in chunks:
        content = c.get("content", "").strip()
        if not content:
            continue
        metadata: dict[str, Any] = {}
        if "page" in c:
            metadata["page"] = c["page"]
        docs.append(Document(page_content=content, metadata=metadata))
    if not docs:
        raise ValueError("No non-empty content in chunks.")
    embeddings = _make_embeddings()
    vectorstore = FAISS.from_documents(docs, embeddings)
    logger.info("Built FAISS index from %d chunks", len(docs))
    return vectorstore


def save_index_to_db(upload_id: str, vectorstore: FAISS) -> None:
    """Serialize FAISS index to temp dir, read as bytes, store in DB."""
    if engine is None:
        raise RuntimeError("Database engine not available")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        vectorstore.save_local(str(path))
        index_bytes = (path / "index.faiss").read_bytes()
        pkl_bytes = (path / "index.pkl").read_bytes()
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT OR REPLACE INTO document_indexes (upload_id, index_blob, docstore_blob) VALUES (:upload_id, :index_blob, :docstore_blob)"
            ),
            {
                "upload_id": upload_id,
                "index_blob": index_bytes,
                "docstore_blob": pkl_bytes,
            },
        )
        conn.commit()
    logger.info("Saved document index for upload_id=%s", upload_id)


def load_index_from_db(upload_id: str) -> FAISS | None:
    """Load FAISS index from DB; returns None if not found."""
    if engine is None:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT index_blob, docstore_blob FROM document_indexes WHERE upload_id = :upload_id"
            ),
            {"upload_id": upload_id},
        ).fetchone()
    if not row:
        return None
    index_bytes = row[0]
    docstore_bytes = row[1]
    embeddings = _make_embeddings()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        (path / "index.faiss").write_bytes(index_bytes)
        (path / "index.pkl").write_bytes(docstore_bytes)
        vectorstore = FAISS.load_local(
            str(path),
            embeddings,
            allow_dangerous_deserialization=True,
        )
    return vectorstore


def search_document(upload_id: str, query: str, k: int = 10) -> list[str]:
    """Return top-k chunk texts for the query. Returns [] if index not found."""
    vs = load_index_from_db(upload_id)
    if vs is None:
        logger.warning("No document index for upload_id=%s", upload_id)
        return []
    docs = vs.similarity_search(query, k=k)
    return [d.page_content for d in docs]
