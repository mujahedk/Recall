from __future__ import annotations

import os
import shutil
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.enums import DocumentStatus

STORAGE_DIR = "storage"


def create_document_from_upload(db: Session, file: UploadFile) -> Document:
    """Save the uploaded PDF to disk and create a Document row.

    The file is stored as storage/doc_{id}.pdf using the DB-assigned ID
    so the filename is deterministic and collision-free.
    """
    os.makedirs(STORAGE_DIR, exist_ok=True)

    original_name = file.filename or "uploaded.pdf"
    title = Path(original_name).stem

    doc = Document(
        title=title,
        status=DocumentStatus.uploaded,
        page_count=None,
        error=None,
        filename=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    disk_name = f"doc_{doc.id}.pdf"
    disk_path = os.path.join(STORAGE_DIR, disk_name)

    file.file.seek(0)
    with open(disk_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    doc.filename = disk_name
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return doc
