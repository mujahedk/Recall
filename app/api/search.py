from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.embeddings import EmbeddingsClient
from app.core.vector_store import VectorStore
from app.db.deps import get_db
from app.models.chunk import Chunk


router = APIRouter(prefix="/search", tags=["search"])


class RebuildResult(BaseModel):
    chunks_indexed: int


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchHit(BaseModel):
    chunk_id: int
    document_id: int
    chunk_index: int
    page_start: int | None
    page_end: int | None
    score: float
    snippet: str


class SearchResponse(BaseModel):
    top_k: int
    hits: list[SearchHit]


@router.post("/rebuild", response_model=RebuildResult)
def rebuild_index(db: Session = Depends(get_db)):
    """Rebuild the FAISS index from all chunks in Postgres.

    Full rebuild is intentional: it is idempotent and avoids stale or
    duplicate vectors. Cost is O(n) embeddings; acceptable at this scale.
    """
    chunks = db.query(Chunk).order_by(Chunk.id.asc()).all()
    if not chunks:
        return RebuildResult(chunks_indexed=0)

    texts = [c.content for c in chunks]
    chunk_ids = [c.id for c in chunks]

    emb = EmbeddingsClient()
    vectors = emb.embed_texts(texts)

    store = VectorStore()
    store.reset()                 # remove any prior index/map on disk
    store.build_new(dim=vectors.shape[1])
    store.add(vectors, chunk_ids)
    store.save()

    return RebuildResult(chunks_indexed=len(chunks))


@router.post("", response_model=SearchResponse)
def semantic_search(payload: SearchRequest, db: Session = Depends(get_db)):
    store = VectorStore()
    store.load()

    if store.index is None or not store.id_map:
        raise HTTPException(
            status_code=400, detail="Vector index not built. Run POST /search/rebuild first.")

    emb = EmbeddingsClient()
    qvec = emb.embed_texts([payload.query])  # shape (1, dim)

    chunk_ids, scores = store.search(qvec[0], top_k=payload.top_k)

    if not chunk_ids:
        return SearchResponse(top_k=payload.top_k, hits=[])

    # Fetch chunks; preserve FAISS order
    chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
    by_id = {c.id: c for c in chunks}

    hits: list[SearchHit] = []
    for cid, sc in zip(chunk_ids, scores):
        c = by_id.get(cid)
        if not c:
            continue
        snippet = (c.content[:240] +
                   "...") if len(c.content) > 240 else c.content
        hits.append(
            SearchHit(
                chunk_id=c.id,
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                page_start=c.page_start,
                page_end=c.page_end,
                score=sc,
                snippet=snippet,
            )
        )

    return SearchResponse(top_k=payload.top_k, hits=hits)
