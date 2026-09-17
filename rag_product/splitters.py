"""Structure-aware text splitting for short, medium, and long documents."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rag_product.schemas import Chunk, Document


SECTION_HEADING_RE = re.compile(
    r"^\s*(#{1,6}\s+.+|第[一二三四五六七八九十百千万0-9]+[章节篇部分].+|[0-9]+(?:\.[0-9]+)*[、.]\s*.+)$"
)
SENTENCE_RE = re.compile(r"(?<=[。！？!?；;.!?])\s+")


@dataclass(frozen=True)
class Section:
    index: int
    title: str
    text: str
    start_char: int
    end_char: int


def classify_text_length(text: str) -> str:
    char_count = len(text)
    if char_count <= 5_000:
        return "short"
    if char_count <= 30_000:
        return "medium"
    return "long"


def extract_sections(text: str) -> list[Section]:
    """Extract markdown/Chinese/numbered sections, falling back to one section."""
    lines = text.splitlines(keepends=True)
    headings: list[tuple[int, str]] = []
    cursor = 0
    for line in lines:
        stripped = line.strip()
        if stripped and SECTION_HEADING_RE.match(stripped):
            headings.append((cursor, _clean_heading(stripped)))
        cursor += len(line)

    if not headings:
        title = "全文"
        return [Section(index=0, title=title, text=text.strip(), start_char=0, end_char=len(text))]

    sections = []
    for index, (start, title) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        section_text = text[start:end].strip()
        if section_text:
            sections.append(
                Section(
                    index=index,
                    title=title,
                    text=section_text,
                    start_char=start,
                    end_char=end,
                )
            )
    return sections


def split_document(document: Document) -> list[Chunk]:
    strategy = classify_text_length(document.text)
    sections = extract_sections(document.text)
    chunks: list[Chunk] = []

    if strategy == "short":
        return _split_short_document(document, sections, strategy)

    if strategy == "medium":
        target_size, overlap = 1_800, 220
        include_section_summaries = False
    else:
        target_size, overlap = 1_200, 180
        include_section_summaries = True

    for section in sections:
        if include_section_summaries:
            chunks.append(_make_section_chunk(document, section, strategy))

        windows = _section_windows(section.text, target_size=target_size, overlap=overlap)
        for window_index, text in enumerate(windows):
            chunks.append(
                _make_leaf_chunk(
                    document=document,
                    section=section,
                    text=text,
                    strategy=strategy,
                    window_index=window_index,
                )
            )
    return chunks


def _split_short_document(document: Document, sections: list[Section], strategy: str) -> list[Chunk]:
    chunks = []
    for section in sections:
        chunks.append(
            _make_leaf_chunk(
                document=document,
                section=section,
                text=section.text,
                strategy=strategy,
                window_index=0,
            )
        )
    return chunks


def _make_section_chunk(document: Document, section: Section, strategy: str) -> Chunk:
    summary_text = _section_summary_text(section)
    metadata = _base_metadata(document, section, strategy)
    metadata.update(
        {
            "chunk_type": "section_summary",
            "chunk_index": section.index,
            "location": f"section:{section.index}",
        }
    )
    return Chunk(
        chunk_id=f"{document.doc_id}-section-{section.index}",
        doc_id=document.doc_id,
        text=summary_text,
        metadata=metadata,
    )


def _make_leaf_chunk(
    document: Document,
    section: Section,
    text: str,
    strategy: str,
    window_index: int,
) -> Chunk:
    metadata = _base_metadata(document, section, strategy)
    metadata.update(
        {
            "chunk_type": "leaf",
            "chunk_index": window_index,
            "parent_chunk_id": f"{document.doc_id}-section-{section.index}",
            "location": f"section:{section.index}/chunk:{window_index}",
        }
    )
    return Chunk(
        chunk_id=f"{document.doc_id}-s{section.index}-c{window_index}",
        doc_id=document.doc_id,
        text=text,
        metadata=metadata,
    )


def _base_metadata(document: Document, section: Section, strategy: str) -> dict:
    metadata = dict(document.metadata)
    metadata.update(
        {
            "rag_strategy": strategy,
            "section_index": section.index,
            "section_title": section.title,
            "section_start_char": section.start_char,
            "section_end_char": section.end_char,
        }
    )
    return metadata


def _section_summary_text(section: Section) -> str:
    paragraphs = _paragraphs(section.text)
    preview = "\n\n".join(paragraphs[:3]) if paragraphs else section.text
    if len(preview) > 900:
        preview = preview[:900].rsplit(" ", 1)[0] or preview[:900]
    return f"{section.title}\n\n{preview}"


def _section_windows(text: str, target_size: int, overlap: int) -> list[str]:
    units = _paragraphs(text)
    if not units:
        units = _sentences(text)
    windows = _pack_units(units, target_size=target_size, overlap=overlap)
    expanded: list[str] = []
    for window in windows:
        if len(window) <= target_size * 1.35:
            expanded.append(window)
        else:
            expanded.extend(_pack_units(_sentences(window), target_size=target_size, overlap=overlap))
    return expanded


def _pack_units(units: list[str], target_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for unit in units:
        unit = unit.strip()
        if not unit:
            continue
        separator_len = 2 if current else 0
        if current and current_len + separator_len + len(unit) > target_size:
            chunks.append("\n\n".join(current))
            current = _overlap_tail(chunks[-1], overlap)
            current_len = sum(len(item) for item in current) + max(0, len(current) - 1) * 2
        if len(unit) > target_size:
            for piece in _hard_wrap(unit, target_size, overlap):
                if current:
                    chunks.append("\n\n".join(current))
                    current = []
                    current_len = 0
                chunks.append(piece)
            continue
        current.append(unit)
        current_len += separator_len + len(unit)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _overlap_tail(text: str, overlap: int) -> list[str]:
    if overlap <= 0:
        return []
    tail = text[-overlap:].strip()
    return [tail] if tail else []


def _hard_wrap(text: str, target_size: int, overlap: int) -> list[str]:
    pieces = []
    step = max(1, target_size - overlap)
    for start in range(0, len(text), step):
        pieces.append(text[start : start + target_size].strip())
    return [piece for piece in pieces if piece]


def _paragraphs(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in SENTENCE_RE.split(text) if item.strip()]


def _clean_heading(text: str) -> str:
    text = re.sub(r"^#{1,6}\s*", "", text).strip()
    return text[:80]
