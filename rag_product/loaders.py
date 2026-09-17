"""Local document loaders for RAG experiments."""

from __future__ import annotations

import hashlib
import os

from rag_product.schemas import Document


SUPPORTED_EXTENSIONS = {".txt", ".md"}


def load_text_file(file_path: str) -> Document:
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Only {sorted(SUPPORTED_EXTENSIONS)} files are supported.")
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    abs_path = os.path.abspath(file_path)
    doc_id = hashlib.sha1(abs_path.encode("utf-8")).hexdigest()[:16]
    return Document(
        doc_id=doc_id,
        text=text,
        metadata={
            "source": abs_path,
            "filename": os.path.basename(file_path),
            "extension": ext,
            "char_count": len(text),
        },
    )
