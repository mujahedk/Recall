from __future__ import annotations

import json
import os
from typing import List, Tuple, Optional

import faiss
import numpy as np


class VectorStore:
    """
    Persistent FAISS index + mapping:
      - storage/faiss.index
      - storage/faiss_map.json  (list[int] of chunk_ids)
    """

    def __init__(self, storage_dir: str = "storage") -> None:
        self.storage_dir = storage_dir
        self.index_path = os.path.join(storage_dir, "faiss.index")
        self.map_path = os.path.join(storage_dir, "faiss_map.json")

        self.index: Optional[faiss.Index] = None
        self.id_map: List[int] = []  # position -> chunk_id

    def load(self) -> None:
        os.makedirs(self.storage_dir, exist_ok=True)

        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        else:
            self.index = None

        if os.path.exists(self.map_path):
            with open(self.map_path, "r", encoding="utf-8") as f:
                self.id_map = json.load(f)
        else:
            self.id_map = []

    def save(self) -> None:
        if self.index is None:
            raise RuntimeError("No index to save.")
        faiss.write_index(self.index, self.index_path)
        with open(self.map_path, "w", encoding="utf-8") as f:
            json.dump(self.id_map, f)

    def reset(self) -> None:
        """Clear the in-memory index and remove the on-disk files."""
        self.index = None
        self.id_map = []
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        if os.path.exists(self.map_path):
            os.remove(self.map_path)

    def build_new(self, dim: int) -> None:
        """
        Cosine similarity via inner product on normalized vectors.
        So we use IndexFlatIP (inner product).
        """
        self.index = faiss.IndexFlatIP(dim)
        self.id_map = []

    def add(self, vectors: np.ndarray, chunk_ids: List[int]) -> None:
        """
        vectors: shape (n, dim), float32, normalized.
        chunk_ids: length n, DB chunk IDs.
        """
        if self.index is None:
            raise RuntimeError(
                "Index not initialized. Call build_new(dim) first.")
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)
        if vectors.ndim != 2:
            raise ValueError("vectors must be 2D (n, dim)")
        if len(chunk_ids) != vectors.shape[0]:
            raise ValueError("chunk_ids length must match vectors rows")

        self.index.add(vectors)
        self.id_map.extend(chunk_ids)

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> Tuple[List[int], List[float]]:
        """
        query_vec: shape (dim,) or (1, dim), float32, normalized.
        Returns (chunk_ids, scores) in descending similarity.
        """
        if self.index is None:
            return ([], [])
        if query_vec.ndim == 1:
            query_vec = query_vec.reshape(1, -1)
        if query_vec.dtype != np.float32:
            query_vec = query_vec.astype(np.float32)

        scores, idxs = self.index.search(query_vec, top_k)
        idxs_list = idxs[0].tolist()
        scores_list = scores[0].tolist()

        chunk_ids: List[int] = []
        chunk_scores: List[float] = []
        for pos, sc in zip(idxs_list, scores_list):
            if pos == -1:
                continue
            if pos < 0 or pos >= len(self.id_map):
                continue
            chunk_ids.append(self.id_map[pos])
            chunk_scores.append(float(sc))

        return (chunk_ids, chunk_scores)
