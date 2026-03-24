from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.core.embeddings import EmbeddingsClient
from app.core.vector_store import VectorStore


def rebuild_vector_index(db: Session) -> int:
    chunks = db.query(Chunk).order_by(Chunk.id.asc()).all()
    if not chunks:
        store = VectorStore()
        store.reset()
        return 0

    texts = [c.content for c in chunks]
    chunk_ids = [c.id for c in chunks]

    emb = EmbeddingsClient()
    vectors = emb.embed_texts(texts, batch_size=64)

    store = VectorStore()
    store.reset()
    store.build_new(dim=vectors.shape[1])
    store.add(vectors, chunk_ids)
    store.save()

    return len(chunks)
