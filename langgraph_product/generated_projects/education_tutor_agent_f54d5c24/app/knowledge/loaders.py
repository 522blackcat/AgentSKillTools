"""Document loaders for text, Markdown, PDF, and Word files."""

from __future__ import annotations

import io
from pathlib import Path


TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml"}
WORD_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}


def load_document_text(filename: str, payload: bytes, fallback_text: str = "") -> tuple[str, str]:
    suffix = Path(filename or "").suffix.lower()
    if fallback_text and not payload:
        return fallback_text, "text"
    if suffix in TEXT_EXTENSIONS or not suffix:
        return payload.decode("utf-8"), suffix.lstrip(".") or "text"
    if suffix in PDF_EXTENSIONS:
        return _load_pdf(payload), "pdf"
    if suffix in WORD_EXTENSIONS:
        return _load_docx(payload), "docx"
    raise ValueError(f"unsupported document type: {suffix}")


def _load_pdf(payload: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("pypdf is required to ingest PDF files") from exc
    reader = PdfReader(io.BytesIO(payload))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"# page {index}\n{text.strip()}")
    return "\n\n".join(pages)


def _load_docx(payload: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise ValueError("python-docx is required to ingest Word files") from exc
    document = Document(io.BytesIO(payload))
    paragraphs = [item.text.strip() for item in document.paragraphs if item.text.strip()]
    return "\n\n".join(paragraphs)
