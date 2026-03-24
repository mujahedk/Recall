from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.schemas import ChunkCreateResult, ChunkOut, DocumentOut
from app.db.deps import get_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.extract import extract_document_to_pages_json
from app.services.chunking import chunk_document_from_pages_json

import os
import re
import json

router = APIRouter(prefix="/documents", tags=["documents"])

STORAGE_DIR = "storage"
MAX_UPLOAD_MB = 25


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
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    title = _safe_title(file.filename)
    doc = Document(title=title, status=DocumentStatus.uploaded)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    os.makedirs(STORAGE_DIR, exist_ok=True)
    stored_name = f"doc_{doc.id}.pdf"
    path = os.path.join(STORAGE_DIR, stored_name)

    contents = file.file.read()
    if len(contents) > MAX_UPLOAD_MB * 1024 * 1024:
        doc.status = DocumentStatus.failed
        doc.error = f"File too large (>{MAX_UPLOAD_MB}MB)"
        db.commit()
        raise HTTPException(status_code=413, detail=f"File too large (>{MAX_UPLOAD_MB}MB)")

    with open(path, "wb") as f:
        f.write(contents)

    doc.filename = stored_name
    db.commit()
    db.refresh(doc)

    return doc


@router.post("/{doc_id}/extract", response_model=DocumentOut)
def extract_document_text(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        extract_document_to_pages_json(db=db, doc_id=doc_id)
        db.refresh(doc)
        return doc
    except Exception as e:
        doc.status = DocumentStatus.failed
        doc.error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")


@router.get("/{doc_id}/pages")
def get_extracted_pages(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages_path = os.path.join(STORAGE_DIR, f"doc_{doc.id}.pages.json")
    if not os.path.exists(pages_path):
        raise HTTPException(
            status_code=404, detail="Extracted pages not found. Run /extract first.")

    with open(pages_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/{doc_id}/chunk", response_model=ChunkCreateResult)
def chunk_document(
    doc_id: int,
    db: Session = Depends(get_db),
    chunk_size: int = 1200,
    overlap: int = 200,
    delete_existing: bool = True,
):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        result = chunk_document_from_pages_json(
            db=db,
            doc_id=doc_id,
            chunk_size=chunk_size,
            overlap=overlap,
            delete_existing=delete_existing,
        )
        return ChunkCreateResult(
            document_id=doc.id,
            deleted_existing=0,
            created=result["chunks_created"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{doc_id}/chunks", response_model=list[ChunkOut])
def list_chunks(doc_id: int, db: Session = Depends(get_db), limit: int = 20, offset: int = 0):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == doc.id)
        .order_by(Chunk.chunk_index.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return chunks


@router.delete("/{doc_id}/chunks")
def delete_chunks(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    deleted = db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
    db.commit()

    return {
        "document_id": doc.id,
        "deleted_chunks": deleted,
    }


