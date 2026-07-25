"""Splits DocSections (from doc_parser.py) or raw Jira text into
embedding-ready chunks, scoped to a requirement/section where possible."""

from __future__ import annotations

from dataclasses import dataclass

from src.ingestion.doc_parser import DocSection

MAX_CHARS = 1000
OVERLAP_CHARS = 150


@dataclass
class Chunk:
    id: str
    text: str
    section: str | None
    source_type: str  # "doc" | "jira"
    source_id: str
    order: int
    module: str | None = None


def _split_text(text: str, max_chars: int = MAX_CHARS, overlap_chars: int = OVERLAP_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    pieces: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 1 > max_chars:
            pieces.append(current)
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = f"{tail}\n{para}" if tail else para
        else:
            current = f"{current}\n{para}" if current else para
    if current:
        pieces.append(current)
    return pieces


def chunk_sections(
    sections: list[DocSection], source_type: str, source_id: str, module: str | None = None
) -> list[Chunk]:
    chunks: list[Chunk] = []
    order = 0
    for section in sections:
        for piece in _split_text(section.text):
            chunks.append(
                Chunk(
                    id=f"{source_id}::{order}",
                    text=piece,
                    section=section.heading,
                    source_type=source_type,
                    source_id=source_id,
                    order=order,
                    module=module,
                )
            )
            order += 1
    return chunks


def chunk_text(
    text: str, source_type: str, source_id: str, section: str | None = None, module: str | None = None
) -> list[Chunk]:
    """For sources without pre-parsed sections (e.g. a Jira description/comment blob)."""
    return chunk_sections([DocSection(heading=section, text=text, order=0)], source_type, source_id, module=module)
