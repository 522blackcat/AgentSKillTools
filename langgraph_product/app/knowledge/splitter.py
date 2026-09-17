"""Structure-aware document splitter."""

from __future__ import annotations

import re


HEADING_RE = re.compile(r"^\s*(#{1,6}\s+.+|第[一二三四五六七八九十百千万0-9]+[章节篇部分].+|[0-9]+(?:\.[0-9]+)*[、.]\s*.+)$")


def split_text(text: str, target_size: int = 1200, overlap: int = 160) -> list[dict]:
    sections = _sections(text)
    chunks: list[dict] = []
    for section_index, (title, body) in enumerate(sections):
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", body) if item.strip()]
        if not paragraphs:
            paragraphs = [body]
        current: list[str] = []
        current_len = 0
        chunk_index = 0
        for paragraph in paragraphs:
            if current and current_len + len(paragraph) + 2 > target_size:
                chunk_text = "\n\n".join(current)
                chunks.append(_chunk(section_index, chunk_index, title, chunk_text))
                chunk_index += 1
                tail = chunk_text[-overlap:].strip()
                current = [tail] if tail else []
                current_len = len(tail)
            current.append(paragraph)
            current_len += len(paragraph) + 2
        if current:
            chunks.append(_chunk(section_index, chunk_index, title, "\n\n".join(current)))
    return chunks


def _sections(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines(keepends=True)
    starts: list[tuple[int, str]] = []
    cursor = 0
    for line in lines:
        stripped = line.strip()
        if stripped and HEADING_RE.match(stripped):
            starts.append((cursor, re.sub(r"^#{1,6}\s*", "", stripped)[:120]))
        cursor += len(line)
    if not starts:
        return [("全文", text)]
    result = []
    for index, (start, title) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        result.append((title, text[start:end].strip()))
    return result


def _chunk(section_index: int, chunk_index: int, title: str, text: str) -> dict:
    return {
        "section_index": section_index,
        "chunk_index": chunk_index,
        "section_title": title,
        "location": f"section:{section_index}/chunk:{chunk_index}",
        "text": text,
    }
