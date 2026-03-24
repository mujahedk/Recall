from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document

_NULL_RE = re.compile(r"\x00")


def sanitize_text(s: str) -> str:
    return _NULL_RE.sub("", s or "")


def _pages_json_path(doc_id: int) -> str:
    return os.path.join("storage", f"doc_{doc_id}.pages.json")


@dataclass
class ChunkConfig:
    chunk_size: int = 1200
    overlap: int = 200
    min_chars: int = 200


def _build_full_text_and_ranges(
    pages: List[Dict[str, Any]],
) -> Tuple[str, List[Tuple[int, int, int]]]:
    """Concatenate all page texts and record (page_num, start_char, end_char) for each page.

    The newline separator between pages prevents words from two adjacent pages
    being joined into a single token at the boundary.
    """
    full_parts: List[str] = []
    ranges: List[Tuple[int, int, int]] = []
    cursor = 0

    for p in pages:
        page_num = int(p.get("page"))
        text = sanitize_text(p.get("text") or "")
        part = text + "\n"
        start = cursor
        cursor += len(part)
        end = cursor

        full_parts.append(part)
        ranges.append((page_num, start, end))

    return "".join(full_parts).strip(), ranges


def _pages_for_window(
    ranges: List[Tuple[int, int, int]],
    start: int,
    end: int,
) -> Tuple[int | None, int | None]:
    page_start = None
    page_end = None

    for page_num, p_start, p_end in ranges:
        # early break: if this page starts after the window ends
        if p_start >= end:
            break
        intersects = not (end <= p_start or start >= p_end)
        if intersects:
            if page_start is None:
                page_start = page_num
            page_end = page_num

    return page_start, page_end


def _make_chunks(pages: List[Dict[str, Any]], cfg: ChunkConfig) -> List[Dict[str, Any]]:
    full_text, ranges = _build_full_text_and_ranges(pages)
    if not full_text:
        return []

    overlap = min(cfg.overlap, max(cfg.chunk_size - 1, 0))

    chunks: List[Dict[str, Any]] = []
    start = 0
    chunk_index = 0
    n = len(full_text)

    while start < n:
        end = min(start + cfg.chunk_size, n)
        raw = sanitize_text(full_text[start:end]).strip()

        if len(raw) >= cfg.min_chars:
            p_start, p_end = _pages_for_window(ranges, start, end)
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "content": raw,
                    "page_start": p_start,
                    "page_end": p_end,
                }
            )
            chunk_index += 1

        if end == n:
            break

        # move forward with overlap; ensure progress
        start = max(end - overlap, start + 1)

    return chunks


def chunk_document_from_pages_json(
    db: Session,
    doc_id: int,
    delete_existing: bool = True,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> Dict[str, Any]:
    """Read storage/doc_{id}.pages.json and insert Chunk rows into Postgres."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError(f"Document {doc_id} not found")

    pages_path = _pages_json_path(doc_id)
    if not os.path.exists(pages_path):
        raise ValueError(
            f"Pages JSON not found. Run extraction first: {pages_path}")

    with open(pages_path, "r", encoding="utf-8") as f:
        pages = json.load(f)

    cfg = ChunkConfig(chunk_size=chunk_size, overlap=overlap)

    payloads = _make_chunks(pages, cfg)

    if delete_existing:
        db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
        db.commit()

    rows: List[Chunk] = []
    for p in payloads:
        rows.append(
            Chunk(
                document_id=doc_id,
                chunk_index=p["chunk_index"],
                page_start=p["page_start"],
                page_end=p["page_end"],
                content=p["content"],
            )
        )

    if rows:
        db.add_all(rows)
        db.commit()

    return {"doc_id": doc_id, "chunks_created": len(rows), "pages_path": pages_path}
