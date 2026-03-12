"""
icons.py

Builds and serves a FAISS semantic search index over Phosphor icons.

- Reads icons from icon/icons.json  (embedded SVG + tags)
- Embeds each icon as  "<name> <tags>"  using Google Gemini embeddings
- Saves the FAISS index to FAISS_INDEX_PATH (default: icon/faiss_icon_index/)
- On startup, rebuilds the index only if it doesn't already exist
- Exposes search_icon(query, k=1) → list of dicts with name + svg content

Config (all via .env):
    GEMINI_API_KEY         – required, shared with the main agent
    ICON_EMBEDDING_MODEL   – Gemini embedding model for icons (default: models/gemini-embedding-001)
    EMBEDDING_MODEL        – optional; if set, used as fallback when ICON_EMBEDDING_MODEL unset
    ICON_STYLE_FILTER      – filter icons by style   (default: outline)
                             set to empty string "" to index all styles
    FAISS_INDEX_PATH       – where to persist the index
                             (default: <this file's dir>/faiss_icon_index)

Usage:
    from icon.icons import ensure_index, search_icon

    # call once at app startup (sync, safe to call from asynccontextmanager)
    ensure_index()

    # query at any time
    results = search_icon("rocket launch", k=3)
    # → [{"name": "rocket", "svg": "<svg…/>", "tags": "…"}, …]
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent                                   # backend/icon/
_ICONS_JSON   = _HERE / "icons.json"
_INDEX_DIR    = Path(os.getenv("FAISS_INDEX_PATH", str(_HERE / "faiss_icon_index")))
_EMBED_MODEL  = os.getenv("ICON_EMBEDDING_MODEL", "models/gemini-embedding-001")
_STYLE_FILTER = os.getenv("ICON_STYLE_FILTER", "outline")

# Module-level singleton — built/loaded once, reused for every query
_vectorstore: FAISS | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_embeddings() -> GoogleGenerativeAIEmbeddings:
    api_key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Set GOOGLE_GENERATIVE_AI_API_KEY or GEMINI_API_KEY in .env")
    return GoogleGenerativeAIEmbeddings(
        model=_EMBED_MODEL,
        google_api_key=api_key,
    )


def _load_documents() -> list[Document]:
    """Parse icons.json → one LangChain Document per icon (filtered by style)."""
    with open(_ICONS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs: list[Document] = []
    for icon in data["icons"]:
        if _STYLE_FILTER and icon.get("style") != _STYLE_FILTER:
            continue

        name = icon["name"]
        # Strip the *new* marker that Phosphor uses for recently added icons
        tags = icon.get("tags", "").replace("*new*,", "").replace("*new*", "").strip(",")
        # page_content is what gets embedded: name + semantic keywords
        text = f"{name} {tags}".strip()

        docs.append(Document(
            page_content=text,
            metadata={
                "name":  name,
                "style": icon.get("style", ""),
                "tags":  tags,
                # Inline SVG stored in metadata — returned directly to callers,
                # no extra disk I/O needed at query time.
                "svg":   icon.get("content", ""),
            },
        ))

    logger.info(
        "Loaded %d icons (style_filter=%r) from %s",
        len(docs), _STYLE_FILTER, _ICONS_JSON,
    )
    return docs


def _build_index() -> FAISS:
    """Embed all icons and persist the FAISS index to disk."""
    logger.info("Building FAISS icon index → %s", _INDEX_DIR)
    docs = _load_documents()
    if not docs:
        raise ValueError(
            f"No icons matched style_filter={_STYLE_FILTER!r}. "
            "Check ICON_STYLE_FILTER in your .env."
        )
    embeddings = _make_embeddings()
    vectorstore = FAISS.from_documents(docs, embeddings)
    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(_INDEX_DIR))
    logger.info("FAISS icon index saved (%d icons) → %s", len(docs), _INDEX_DIR)
    return vectorstore


def _load_index() -> FAISS:
    """Load a previously saved FAISS index from disk."""
    logger.info("Loading FAISS icon index from %s", _INDEX_DIR)
    embeddings = _make_embeddings()
    return FAISS.load_local(
        str(_INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def ensure_index() -> None:
    """
    Build the FAISS index if it doesn't exist, then load it into memory.

    Call exactly once at application startup (e.g. from FastAPI lifespan).
    Subsequent calls are no-ops if the index is already loaded.
    """
    global _vectorstore

    if _vectorstore is not None:
        logger.debug("ensure_index: already loaded, skipping")
        return

    index_file = _INDEX_DIR / "index.faiss"
    logger.info("ensure_index: index_file=%s exists=%s", index_file, index_file.exists())
    try:
        if index_file.exists():
            logger.info("ensure_index: loading from disk")
            _vectorstore = _load_index()
        else:
            logger.info("ensure_index: building new index (first run or index missing)")
            _vectorstore = _build_index()
    except Exception as exc:
        logger.exception("ensure_index: failed → %s", exc)
        raise

    logger.info("Icon FAISS index ready (model=%s, index=%s)", _EMBED_MODEL, _INDEX_DIR)


def rebuild_index() -> None:
    """
    Force a full rebuild of the index (e.g. after icons.json is updated).
    Replaces the on-disk and in-memory index.
    """
    global _vectorstore
    _vectorstore = _build_index()
    logger.info("Icon FAISS index rebuilt.")


def svg_to_png_bytes(svg: str, output_width: int = 64, output_height: int = 64) -> bytes:
    """
    Convert SVG string to PNG bytes using resvg_py (Rust backend, no Cairo).
    Returns PNG bytes suitable for Slides API.
    """
    from io import BytesIO

    try:
        import resvg_py
        from PIL import Image

        png_bytes = resvg_py.svg_to_bytes(svg_string=svg)
        img = Image.open(BytesIO(png_bytes))
        img = img.resize((output_width, output_height), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    except ImportError:
        raise RuntimeError(
            "resvg_py required for icon-to-slide. Run: pip install resvg_py Pillow"
        )
    except Exception as e:
        raise RuntimeError(f"SVG to PNG conversion failed: {e}") from e


def get_icon_by_name(name: str) -> dict | None:
    """
    Look up an icon by exact name from icons.json. Returns {"name", "svg", "tags"} or None.
    """
    with open(_ICONS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    for icon in data.get("icons", []):
        if icon.get("name") == name:
            return {
                "name": name,
                "svg": icon.get("content", ""),
                "tags": icon.get("tags", ""),
            }
    return None


def search_icon(query: str, k: int = 1) -> list[dict]:
    """
    Semantic similarity search over the icon index.

    Args:
        query: natural-language description, e.g. "rocket launch", "warning sign"
        k:     number of results to return (default 1)

    Returns:
        List of dicts:
            [{"name": "rocket", "svg": "<svg…/>", "tags": "space,launch,…"}]

    Raises:
        RuntimeError if ensure_index() has not been called yet.
    """
    logger.info("search_icon: query=%r k=%d", query, k)

    if _vectorstore is None:
        logger.error("search_icon: _vectorstore is None (ensure_index not called or failed at startup)")
        raise RuntimeError(
            "Icon index not initialised. Call ensure_index() at app startup."
        )

    try:
        results = _vectorstore.similarity_search(query, k=k)
    except Exception as exc:
        logger.exception("search_icon: similarity_search failed (embedding/FAISS?)")
        raise

    logger.info("search_icon: found %d result(s) for %r", len(results), query)
    return [
        {
            "name": doc.metadata["name"],
            "svg":  doc.metadata["svg"],
            "tags": doc.metadata["tags"],
        }
        for doc in results
    ]
