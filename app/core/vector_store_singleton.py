from app.core.vector_store import VectorStore


def get_vector_store() -> VectorStore:
    """Load the FAISS index fresh from disk on each call.

    Intentionally not cached: after every rebuild the on-disk index changes,
    and a stale in-memory reference would silently return old results.
    IndexFlatIP at a few thousand vectors loads in <10ms, which is fine.
    """
    store = VectorStore()
    store.load()
    return store
