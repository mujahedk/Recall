from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api._utils import normalize_query
from app.api.schemas import AnswerCitation, AnswerRequest, AnswerResponse
from app.core.embeddings import EmbeddingsClient
from app.core.llm import LLMClient
from app.core.vector_store_singleton import get_vector_store
from app.db.deps import get_db
from app.models.chunk import Chunk
from app.models.document import Document

router = APIRouter(prefix="/answer", tags=["answer"])

# Minimum cosine score and keyword overlap required before calling the LLM.
# Below these thresholds the retrieved context is unlikely to be relevant,
# and sending it to the model wastes tokens and produces low-confidence answers.
MIN_SCORE = 0.25
MIN_KEYWORD_OVERLAP = 1


@router.post("", response_model=AnswerResponse)
def answer_question(payload: AnswerRequest, db: Session = Depends(get_db)):
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

    # Oversample so we have room to filter and dedupe before picking top_k
    chunk_ids, scores = store.search(qvec, top_k=payload.top_k * 3)
    if not chunk_ids:
        return AnswerResponse(
            query=q,
            answer="I couldn't find relevant context in your indexed documents.",
            citations=[],
        )

    chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
    by_id = {c.id: c for c in chunks}

    filtered = []
    for cid, sc in zip(chunk_ids, scores):
        c = by_id.get(cid)
        if not c:
            continue
        if payload.document_id is not None and c.document_id != payload.document_id:
            continue
        filtered.append((c, float(sc)))

    if not filtered:
        return AnswerResponse(
            query=q, answer="No results matched your document filter.", citations=[]
        )

    doc_ids = list({c.document_id for c, _ in filtered})
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    doc_title = {d.id: d.title or "Untitled" for d in docs}

    # Deduplicate by page span so two overlapping chunks from the same page
    # don't both consume a context slot.
    seen: set = set()
    chosen: list = []
    for c, sc in filtered:
        key = (c.document_id, c.page_start, c.page_end)
        if key in seen:
            continue
        seen.add(key)
        chosen.append((c, sc))
        if len(chosen) >= payload.top_k:
            break

    # Relevance guardrail: skip the LLM if the best chunk is too dissimilar
    # or has no keyword overlap with the query. This avoids generating an
    # answer grounded in irrelevant context.
    best_score = chosen[0][1] if chosen else 0.0
    query_terms = {w.lower() for w in q.split() if len(w) > 3}
    context_text = " ".join(c.content.lower() for c, _ in chosen)
    keyword_overlap = sum(1 for t in query_terms if t in context_text)

    if best_score < MIN_SCORE or keyword_overlap < MIN_KEYWORD_OVERLAP:
        return AnswerResponse(
            query=q,
            answer=(
                "I don't have enough relevant information in your indexed documents to answer this "
                "with citations. Try uploading a document that covers this topic, then re-index and ask again."
            ),
            citations=[],
        )

    citations: list[AnswerCitation] = []
    context_blocks: list[str] = []

    for i, (c, sc) in enumerate(chosen, start=1):
        # Truncate long chunks so the context window stays reasonable.
        # The full chunk is still indexed; only the prompt is trimmed here.
        content = c.content[:2000] + "..." if len(c.content) > 2000 else c.content

        citations.append(
            AnswerCitation(
                n=i,
                doc_id=c.document_id,
                doc_title=doc_title.get(c.document_id, "Untitled"),
                chunk_id=c.id,
                page_start=c.page_start,
                page_end=c.page_end,
                snippet=(c.content[:280] + "...") if len(c.content) > 280 else c.content,
                score=round(sc, 4),
            )
        )

        pages = f"(pages {c.page_start}-{c.page_end})" if c.page_start is not None else ""
        context_blocks.append(
            f"[{i}] {doc_title.get(c.document_id, 'Untitled')} {pages}\n{content}"
        )

    context = "\n\n".join(context_blocks)
    llm = LLMClient()
    answer_text = llm.generate_answer(query=q, context=context)

    return AnswerResponse(query=q, answer=answer_text, citations=citations)
