from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.schemas import DocumentOut
from app.db.deps import get_db
from app.models.document import Document, DocumentStatus

import os
import re

router = APIRouter(prefix="/documents", tags=["documents"])

STORAGE_DIR = "storage"
MAX_MB = 25  # MVP limit


def _safe_title(filename: str) -> str:
    """Turn 'My File.pdf' into a reasonable title."""
    base = os.path.splitext(filename)[0]
    base = re.sub(r"[_\-]+", " ", base).strip()
    return base[:255] if base else "Untitled"


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return docs


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/upload", response_model=DocumentOut)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # 1) Basic validation
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    # Content-Type can be unreliable, so we check extension too (MVP)
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Only PDF uploads are supported in MVP")

    # 2) Create a Document row first (gives us a stable doc_id)
    title = _safe_title(file.filename)
    doc = Document(title=title, status=DocumentStatus.processing)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 3) Save file to disk using doc_id for deterministic naming
    os.makedirs(STORAGE_DIR, exist_ok=True)
    stored_name = f"doc_{doc.id}.pdf"
    path = os.path.join(STORAGE_DIR, stored_name)

    # Read bytes (MVP: fine for <=25MB; we'll stream later if needed)
    contents = file.file.read()

    max_bytes = MAX_MB * 1024 * 1024
    if len(contents) > max_bytes:
        # mark failed and clean up
        doc.status = DocumentStatus.failed
        doc.error = f"File too large (>{MAX_MB}MB)"
        db.commit()
        raise HTTPException(
            status_code=413, detail=f"File too large (>{MAX_MB}MB)")

    with open(path, "wb") as f:
        f.write(contents)

    # 4) Update doc row with stored filename
    doc.filename = stored_name
    db.commit()
    db.refresh(doc)

    return doc
