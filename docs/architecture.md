# Architecture

## Component overview

```
Browser / curl
     │
     ├── GET /               → Jinja2 UI (home.html)
     ├── POST /ui/upload     → upload + full pipeline (UI path)
     ├── POST /ui/answer     → Q&A with citations (UI path)
     │
     ├── POST /documents/upload    → upload file only
     ├── POST /documents/{id}/extract
     ├── POST /documents/{id}/chunk
     ├── POST /search/rebuild      → embed all chunks → FAISS
     ├── POST /search              → raw FAISS results
     ├── POST /answer              → retrieval + LLM answer
     └── POST /query               → retrieval without generation
```

## Ingestion pipeline

```
PDF file
   │
   ▼
[1] services/extract.py
    PyMuPDF page-by-page text extraction
    → storage/doc_{id}.pages.json
      [{page: 1, text: "..."}, ...]
   │
   ▼
[2] services/chunking.py
    Character-window chunking (1200 chars, 200 overlap)
    Tracks page_start / page_end per chunk
    → Chunk rows in PostgreSQL
   │
   ▼
[3] services/indexing.py  (or api/search.py /rebuild)
    Batch-embeds all chunks via OpenAI text-embedding-3-small
    L2-normalizes vectors → cosine similarity = inner product
    → FAISS IndexFlatIP saved to storage/faiss.index
       + storage/faiss_map.json  (position → chunk_id)
```

## Query / RAG flow

```
User query (string)
   │
   ▼
[1] EmbeddingsClient.embed_texts([query])
    → query vector (1536-dim, normalized)
   │
   ▼
[2] VectorStore.search(query_vec, top_k)
    FAISS IndexFlatIP.search → top-k (chunk position, score) pairs
    positions resolved to chunk_ids via faiss_map.json
   │
   ▼
[3] DB lookup: Chunk rows by chunk_ids
    Optional filter by document_id
    Deduplicate by (document_id, page_start, page_end)
   │
   ▼
[4] Relevance guardrail (answer endpoint only)
    - best cosine score >= 0.25
    - at least 1 query keyword appears in retrieved text
    If fails → return "not enough context" without calling LLM
   │
   ▼
[5] LLMClient.generate_answer(query, context)
    Context: numbered blocks  "[1] Doc Title (pages X-Y)\n<chunk text>"
    System prompt enforces: cite every claim as [n], no hallucination
    Uses OpenAI Responses API (gpt-4.1-mini)
   │
   ▼
[6] Return AnswerResponse
    - answer: string with inline [n] citations
    - citations: [{n, doc_title, page_start, page_end, snippet, score}]
```

## Data model

```
Document
  id            int PK
  title         str
  filename      str          storage/doc_{id}.pdf
  status        enum         uploaded | processing | ready | failed
  page_count    int?
  error         str?
  created_at    datetime

Chunk
  id            int PK
  document_id   int FK → Document
  chunk_index   int          position within document
  page_start    int?
  page_end      int?
  content       str
  created_at    datetime
```

## Storage layout

```
storage/
  doc_{id}.pdf              uploaded PDF
  doc_{id}.pages.json       extracted text per page (intermediate)
  faiss.index               serialized FAISS IndexFlatIP
  faiss_map.json            [chunk_id, ...]  — maps FAISS position to DB id
```

## Key design decisions and tradeoffs

### FAISS IndexFlatIP with L2 normalization
Exact (not approximate) cosine similarity. No quantization or clustering. Correct for a few thousand vectors and fast enough locally. At 100K+ vectors, `IndexIVFFlat` with IVF partitioning would be faster; for this portfolio scale, exact search is the right choice and is easier to explain.

### Character-window chunking
Simple, language-agnostic, and predictable. Semantic chunking (splitting on sentence or paragraph boundaries) would produce better context windows but requires an NLP library and produces variable-length chunks. The 1200/200 char target/overlap was tuned to keep chunks within the embedding model's context window while maintaining enough continuity for retrieval.

### Full rebuild on every index update
Re-embeds all chunks from Postgres on every rebuild. This is correct and idempotent — no stale vectors, no incremental update bugs. At 2K vectors it takes ~5 seconds. The tradeoff is that incremental adds are O(n) total; for 100K+ chunks an incremental strategy (embed only new chunks, append to index) would be needed.

### OpenAI Responses API for generation
Single-turn, context-only RAG. No chat history, no tool use. The system prompt is minimal and strict (cite every claim or don't say it). This prevents hallucination while keeping latency predictable.

### FAISS on disk vs a vector database
FAISS files are portable and require no additional service. The tradeoff: no CRUD on individual vectors (requires full rebuild), no metadata filtering at the vector layer, no horizontal scaling. For a portfolio project this is the right call — it makes the retrieval mechanism transparent and explainable.
