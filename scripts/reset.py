"""
Reset: wipe all documents, chunks, and the FAISS index from a clean state.

Usage:
    python scripts/reset.py          # clears DB + storage/
    make reset                       # same via Makefile

Safe to run repeatedly. Does not touch fixtures/ or the venv.
Requires a running Postgres (make db) and a migrated schema (make migrate).
"""

import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from app.db.session import SessionLocal
from app.services.admin import clear_all_documents


def main() -> None:
    db = SessionLocal()
    try:
        print("Resetting Recall ...")
        result = clear_all_documents(db=db)
        print(f"  Deleted {result['deleted_docs']} document(s)")
        print(f"  Deleted {result['deleted_chunks']} chunk(s)")
        print(f"  Removed {result['removed_files']} file(s) from storage/")
        print("  FAISS index cleared")
        print("Done. Run: make seed  (or make demo)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
