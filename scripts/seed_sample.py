"""
Seed script: run the full ingestion pipeline on a sample PDF.

Demonstrates Bullet 1 of the resume:
    "PDF ingestion (parse → chunk → embed → index)"

Usage (requires a running DB and valid OPENAI_API_KEY in .env):
    python scripts/seed_sample.py              # uses fixtures/sample.pdf
    python scripts/seed_sample.py --pdf path/to/your.pdf

What it does:
    1. Copies the PDF into storage/ under a deterministic name
    2. Runs: extract → chunk → embed → index
    3. Prints page count, chunk count, and vector count
"""

import argparse
import os
import shutil
import sys
import urllib.request

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.extract import extract_document_to_pages_json
from app.services.chunking import chunk_document_from_pages_json
from app.services.indexing import rebuild_vector_index

FIXTURE_PDF = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample.pdf")
FALLBACK_URL = "https://arxiv.org/pdf/1706.03762"


def resolve_pdf(path: str | None) -> str:
    if path:
        if not os.path.exists(path):
            print(f"Error: file not found: {path}")
            sys.exit(1)
        return path

    fixture = os.path.normpath(FIXTURE_PDF)
    if os.path.exists(fixture):
        print(f"Using fixture PDF: {fixture}")
        return fixture

    # Fall back to downloading if the fixture is missing (e.g. fresh clone without LFS)
    print(f"Fixture not found. Downloading from:\n  {FALLBACK_URL}")
    dest = os.path.join("storage", "seed_download.pdf")
    os.makedirs("storage", exist_ok=True)
    try:
        urllib.request.urlretrieve(FALLBACK_URL, dest)
        size_kb = os.path.getsize(dest) / 1024
        print(f"  Downloaded to {dest} ({size_kb:.0f} KB)")
        return dest
    except Exception as e:
        print(f"Download failed: {e}")
        print("Place a PDF at fixtures/sample.pdf or pass --pdf <path>.")
        sys.exit(1)


def create_document(db: Session, pdf_path: str) -> Document:
    filename = os.path.basename(pdf_path)
    title = os.path.splitext(filename)[0].replace("-", " ").replace("_", " ").title()

    doc = Document(
        title=title,
        filename=None,
        status=DocumentStatus.uploaded,
        page_count=None,
        error=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    os.makedirs("storage", exist_ok=True)
    dest = os.path.join("storage", f"doc_{doc.id}.pdf")
    shutil.copy2(pdf_path, dest)

    doc.filename = f"doc_{doc.id}.pdf"
    db.add(doc)
    db.commit()
    db.refresh(doc)

    print(f"  Created Document #{doc.id}: {doc.title!r}")
    return doc


def run_pipeline(db: Session, doc_id: int) -> dict:
    print(f"\nRunning ingestion pipeline for doc #{doc_id} ...")

    print("  [1/3] Extracting text from PDF ...")
    extract_result = extract_document_to_pages_json(db=db, doc_id=doc_id)
    page_count = extract_result["page_count"]
    print(f"        {page_count} pages extracted")

    print("  [2/3] Chunking into overlapping windows (1200 chars, 200 overlap) ...")
    chunk_result = chunk_document_from_pages_json(db=db, doc_id=doc_id, delete_existing=True)
    chunk_count = chunk_result["chunks_created"]
    print(f"        {chunk_count} chunks created")

    doc = db.query(Document).filter(Document.id == doc_id).first()
    doc.status = DocumentStatus.ready
    db.add(doc)
    db.commit()

    print("  [3/3] Embedding and indexing (calls OpenAI API — may take a moment) ...")
    indexed = rebuild_vector_index(db=db)
    print(f"        {indexed} vectors in FAISS index")

    return {"pages": page_count, "chunks": chunk_count, "vectors": indexed}


def main():
    parser = argparse.ArgumentParser(description="Seed Recall with a sample PDF")
    parser.add_argument("--pdf", type=str, default=None, help="Path to a local PDF (default: fixtures/sample.pdf)")
    args = parser.parse_args()

    pdf_path = resolve_pdf(args.pdf)

    db: Session = SessionLocal()
    try:
        doc = create_document(db, pdf_path)
        stats = run_pipeline(db, doc.id)

        print()
        print("=" * 50)
        print("Seed complete")
        print("=" * 50)
        print(f"  Document : #{doc.id} — {doc.title!r}")
        print(f"  Pages    : {stats['pages']}")
        print(f"  Chunks   : {stats['chunks']}")
        print(f"  Vectors  : {stats['vectors']}")
        print()
        print("Open http://localhost:8000 and ask a question about the document.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
