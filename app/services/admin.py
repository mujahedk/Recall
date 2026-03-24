import os
import glob
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.core.vector_store import VectorStore

STORAGE_DIR = "storage"


def clear_all_documents(db: Session) -> dict:
    """Delete all documents, chunks, disk files, and the FAISS index."""
    # Chunks first to respect FK ordering without relying on cascade
    deleted_chunks = db.query(Chunk).delete()
    deleted_docs = db.query(Document).delete()
    db.commit()

    removed_files = 0
    if os.path.exists(STORAGE_DIR):
        for pat in ["doc_*.pdf", "doc_*.pages.json"]:
            for path in glob.glob(os.path.join(STORAGE_DIR, pat)):
                try:
                    os.remove(path)
                    removed_files += 1
                except OSError:
                    pass

    VectorStore(storage_dir=STORAGE_DIR).reset()

    return {
        "deleted_docs": deleted_docs,
        "deleted_chunks": deleted_chunks,
        "removed_files": removed_files,
    }
