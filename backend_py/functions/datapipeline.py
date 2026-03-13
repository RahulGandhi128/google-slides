"""
Data Pipeline — text extraction from supported document formats.
Supported: .docx (paragraphs), .pdf (embedded text). Use extract_text_with_metadata for chunking.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BIG_DOC_PAGE_THRESHOLD = 20
BIG_DOC_CHAR_THRESHOLD = 12_000
CHUNK_CHAR_TARGET = 800
CHUNK_OVERLAP = 200


def extract_text(file_path: str | os.PathLike) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".pdf":
        return _extract_pdf(path)
    raise ValueError(f"Unsupported file type '{suffix}'. Only .docx and .pdf accepted.")


def _extract_docx(path: Path) -> str:
    try:
        import docx
    except ImportError as exc:
        raise ImportError("python-docx required. pip install python-docx") from exc
    doc = docx.Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs) if paragraphs else ""


def _extract_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("pdfplumber required. pip install pdfplumber") from exc
    pages_text = []
    image_only = 0
    with pdfplumber.open(str(path)) as pdf:
        total = len(pdf.pages)
        for page in pdf.pages:
            t = page.extract_text()
            if not t or not t.strip():
                image_only += 1
            else:
                pages_text.append(t.strip())
        if total == 0:
            raise ValueError(f"PDF '{path.name}' has no pages.")
        if image_only == total:
            raise ValueError(f"PDF '{path.name}' is image-only (no selectable text). Use OCR first.")
    return "\n\n".join(pages_text)


def extract_text_with_metadata(file_path: str | os.PathLike) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".docx":
        text = _extract_docx(path)
        return {"text": text, "page_count": 0, "pages": []}
    if suffix == ".pdf":
        try:
            import pdfplumber
        except ImportError as exc:
            raise ImportError("pdfplumber required. pip install pdfplumber") from exc
        pages_text = []
        image_only = 0
        with pdfplumber.open(str(path)) as pdf:
            total = len(pdf.pages)
            for page in pdf.pages:
                t = page.extract_text()
                if not t or not t.strip():
                    image_only += 1
                else:
                    pages_text.append(t.strip())
            if total == 0:
                raise ValueError(f"PDF '{path.name}' has no pages.")
            if image_only == total:
                raise ValueError(f"PDF '{path.name}' is image-only. Use OCR first.")
        return {"text": "\n\n".join(pages_text), "page_count": total, "pages": pages_text}
    raise ValueError(f"Unsupported file type '{suffix}'.")


def chunk_document(
    text: str,
    page_count: int = 0,
    pages: list[str] | None = None,
    format: str = "pdf",
    char_target: int = CHUNK_CHAR_TARGET,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    chunks = []
    if pages:
        for i, page_text in enumerate(pages):
            if not page_text.strip():
                continue
            if len(page_text) <= char_target:
                chunks.append({"content": page_text.strip(), "page": i + 1})
            else:
                start = 0
                while start < len(page_text):
                    end = min(start + char_target, len(page_text))
                    chunk = page_text[start:end].strip()
                    if chunk:
                        chunks.append({"content": chunk, "page": i + 1})
                    start = end - overlap if end < len(page_text) else len(page_text)
        return chunks
    start = 0
    while start < len(text):
        end = min(start + char_target, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"content": chunk})
        start = end - overlap if end < len(text) else len(text)
    return chunks
