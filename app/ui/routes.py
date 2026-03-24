from fastapi import APIRouter, Request, Depends, UploadFile, File, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.api.documents import extract_document_text, chunk_document
from app.api.schemas import AnswerRequest, QueryRequest
from app.api.answer import answer_question
from app.api.query import query_docs
from app.api.search import rebuild_index
from app.services.documents import create_document_from_upload
from app.services.pipeline import process_document
from app.services.indexing import rebuild_vector_index
from app.services.admin import clear_all_documents
from app.core.vector_store import VectorStore

templates = Jinja2Templates(directory="app/ui/templates")
router = APIRouter(tags=["ui"])


def _get_index_size() -> int:
    store = VectorStore()
    store.load()
    return store.index.ntotal if store.index else 0


def _get_chunk_counts(db: Session) -> dict[int, int]:
    rows = db.query(Chunk.document_id, func.count(Chunk.id)).group_by(Chunk.document_id).all()
    return {doc_id: count for doc_id, count in rows}


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.id.desc()).all()
    chunk_counts = _get_chunk_counts(db)
    index_size = _get_index_size()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "docs": docs,
        "chunk_counts": chunk_counts,
        "index_size": index_size,
    })


@router.post("/ui/upload")
async def ui_upload(
    db: Session = Depends(get_db),
    files: list[UploadFile] = File(...),
):
    created_ids: list[int] = []

    for f in files:
        doc = create_document_from_upload(db=db, file=f)
        created_ids.append(doc.id)

    # extract → chunk → set ready/failed per document
    for doc_id in created_ids:
        process_document(db=db, doc_id=doc_id)

    # Rebuild FAISS index from all chunks in one pass
    rebuild_vector_index(db=db)

    return RedirectResponse(url="/", status_code=303)


@router.post("/ui/rebuild")
def ui_rebuild(db: Session = Depends(get_db)):
    rebuild_index(db=db)
    return RedirectResponse(url="/", status_code=303)


@router.post("/ui/docs/{doc_id}/extract")
def ui_extract(doc_id: int, db: Session = Depends(get_db)):
    extract_document_text(doc_id=doc_id, db=db)
    return RedirectResponse(url="/", status_code=303)


@router.post("/ui/docs/{doc_id}/chunk")
def ui_chunk(doc_id: int, db: Session = Depends(get_db)):
    chunk_document(doc_id=doc_id, db=db)
    return RedirectResponse(url="/", status_code=303)


@router.post("/ui/search", response_class=HTMLResponse)
def ui_search(
    request: Request,
    query: str = Form(...),
    top_k: int = Form(default=5),
    db: Session = Depends(get_db),
):
    search_result = query_docs(payload=QueryRequest(query=query, top_k=top_k), db=db)
    docs = db.query(Document).order_by(Document.id.desc()).all()
    chunk_counts = _get_chunk_counts(db)
    index_size = _get_index_size()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "docs": docs,
        "chunk_counts": chunk_counts,
        "index_size": index_size,
        "search_result": search_result,
        "active_tab": "search",
    })


@router.post("/ui/answer", response_class=HTMLResponse)
def ui_answer(
    request: Request,
    query: str = Form(...),
    db: Session = Depends(get_db),
):
    result = answer_question(payload=AnswerRequest(query=query, top_k=6), db=db)
    docs = db.query(Document).order_by(Document.id.desc()).all()
    chunk_counts = _get_chunk_counts(db)
    index_size = _get_index_size()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "docs": docs,
        "chunk_counts": chunk_counts,
        "index_size": index_size,
        "result": result,
        "active_tab": "ask",
    })


@router.post("/ui/clear")
def ui_clear(db: Session = Depends(get_db)):
    clear_all_documents(db=db)
    return RedirectResponse(url="/", status_code=303)
