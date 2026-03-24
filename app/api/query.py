from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api._utils import normalize_query
from app.api.schemas import CitationHit, QueryRequest, QueryResponse
from app.core.embeddings import EmbeddingsClient
from app.core.vector_store_singleton import get_vector_store
from app.db.deps import get_db
from app.models.chunk import Chunk
from app.models.document import Document

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def query_docs(payload: QueryRequest, db: Session = Depends(get_db)):
    """Retrieval-only endpoint: embed the query, search FAISS, return ranked chunks.

    Returns the top-k most similar chunks with cosine scores and page ranges.
    No LLM call is made — this is the pure retrieval step, useful for debugging
    and for demonstrating retrieval separately from generation in interviews.
    """
    q = normalize_query(payload.query)
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    store = get_vector_store()
    if store.index is None or not store.id_map:
        raise HTTPException(
            status_code=400,
            detail="Vector index not built. Upload a document or run POST /search/rebuild.",
        )

    emb = EmbeddingsClient()
    qvec = emb.embed_texts([q])[0]

    # Oversample so document_id filtering still yields top_k after dropping non-matches
    chunk_ids, scores = store.search(qvec, top_k=payload.top_k * 3)

    if not chunk_ids:
        return QueryResponse(query=q, top_k=payload.top_k, hits=[])

    chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
    by_id = {c.id: c for c in chunks}

    filtered_pairs = []
    for cid, sc in zip(chunk_ids, scores):
        c = by_id.get(cid)
        if not c:
            continue
        if payload.document_id is not None and c.document_id != payload.document_id:
            continue
        filtered_pairs.append((c, sc))

    doc_ids = list({c.document_id for c, _ in filtered_pairs})
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    doc_title = {d.id: d.title or "Untitled" for d in docs}

    # Deduplicate by page span (same reason as in answer.py)
    seen: set = set()
    hits: list[CitationHit] = []
    for c, sc in filtered_pairs:
        key = (c.document_id, c.page_start, c.page_end)
        if key in seen:
            continue
        seen.add(key)
        snippet = (c.content[:240] + "...") if len(c.content) > 240 else c.content
        hits.append(
            CitationHit(
                doc_id=c.document_id,
                doc_title=doc_title.get(c.document_id, "Untitled"),
                chunk_id=c.id,
                score=float(sc),
                page_start=c.page_start,
                page_end=c.page_end,
                snippet=snippet,
            )
        )
        if len(hits) >= payload.top_k:
            break

    return QueryResponse(query=q, top_k=payload.top_k, hits=hits)
