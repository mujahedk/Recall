from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.enums import DocumentStatus


def _get_pdf_path(doc: Document) -> str:
    storage_dir = "storage"
    # Prefer filename if set, otherwise deterministic fallback
    filename = doc.filename or f"doc_{doc.id}.pdf"
    return os.path.join(storage_dir, filename)


def _pages_json_path(doc_id: int) -> str:
    return os.path.join("storage", f"doc_{doc_id}.pages.json")


def extract_document_to_pages_json(db: Session, doc_id: int) -> Dict[str, Any]:
    """Extract text from all PDF pages and write storage/doc_{id}.pages.json.

    Output format: [{"page": 1, "text": "..."}, ...]

    NUL bytes are stripped here because Postgres TEXT columns reject them.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError(f"Document {doc_id} not found")

    pdf_path = _get_pdf_path(doc)
    if not os.path.exists(pdf_path):
        raise ValueError(f"PDF file not found on disk at: {pdf_path}")

    os.makedirs("storage", exist_ok=True)

    import fitz  # PyMuPDF

    pages: List[Dict[str, Any]] = []
    try:
        pdf = fitz.open(pdf_path)
        for i in range(len(pdf)):
            text = pdf[i].get_text("text") or ""
            text = text.replace("\x00", "")
            pages.append({"page": i + 1, "text": text})
        page_count = len(pdf)
        pdf.close()
    except Exception as e:
        raise RuntimeError(f"Extraction failed: {e}")

    out_path = _pages_json_path(doc_id)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False)

    doc.page_count = page_count
    doc.status = DocumentStatus.processing
    doc.error = None
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {"doc_id": doc_id, "page_count": page_count, "pages_path": out_path}
