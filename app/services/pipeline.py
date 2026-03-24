from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.extract import extract_document_to_pages_json
from app.services.chunking import chunk_document_from_pages_json


def process_document(db: Session, doc_id: int) -> None:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise ValueError(f"Document {doc_id} not found")

    try:
        doc.status = DocumentStatus.processing
        doc.error = None
        db.add(doc)
        db.commit()

        extract_document_to_pages_json(db=db, doc_id=doc_id)
        chunk_document_from_pages_json(db=db, doc_id=doc_id, delete_existing=True)

        # Lifecycle: mark ready only after both steps succeed
        doc.status = DocumentStatus.ready
        db.add(doc)
        db.commit()

    except Exception as e:
        doc.status = DocumentStatus.failed
        doc.error = str(e)
        db.add(doc)
        db.commit()
        raise
