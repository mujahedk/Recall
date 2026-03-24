from __future__ import annotations

from typing import List
import numpy as np
from openai import OpenAI

from app.core.settings import settings


def _normalize_rows(mat: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalize so inner product ~ cosine similarity."""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class EmbeddingsClient:
    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY missing. Add it to .env")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.EMBEDDING_MODEL

    def embed_texts(self, texts: List[str], batch_size: int = 64) -> np.ndarray:
        """Return a float32 array of shape (len(texts), dim), L2-normalized.

        Sorted by .index to guard against out-of-order responses from the API.
        """
        all_vecs: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            resp = self.client.embeddings.create(model=self.model, input=batch)
            for item in sorted(resp.data, key=lambda x: x.index):
                all_vecs.append(item.embedding)

        mat = np.array(all_vecs, dtype=np.float32)
        return _normalize_rows(mat)
