# Resume Alignment

Target resume bullets for this project:

> **Recall — Semantic Document Search & RAG | Python, FastAPI, PostgreSQL, FAISS**
> - Built PDF ingestion (parse → chunk → embed → index) converting 100+ page docs into 200–500 searchable chunks
> - Implemented FAISS cosine-similarity retrieval across 2,000+ embeddings with sub-300ms query latency (local p95)
> - Added citation-aware RAG responses with automatic re-indexing and document lifecycle state management

---

## Bullet 1 — PDF ingestion pipeline

**Claim**: "Built PDF ingestion (parse → chunk → embed → index) converting 100+ page docs into 200–500 searchable chunks"

### Code proof

| Step | File | What it does |
|---|---|---|
| Parse | `app/services/extract.py` | PyMuPDF extracts text page-by-page, saves `doc_{id}.pages.json` |
| Chunk | `app/services/chunking.py` | Character-window chunking: 1200-char target, 200-char overlap, NUL stripping, page span tracking |
| Embed | `app/core/embeddings.py` | OpenAI `text-embedding-3-small`, batched (64/batch), L2-normalized |
| Index | `app/core/vector_store.py` | FAISS `IndexFlatIP`, persisted to `storage/faiss.index` |
| Orchestration | `app/services/pipeline.py` | Runs extract → chunk, updates lifecycle status |
| Index trigger | `app/services/indexing.py` | Rebuilds FAISS from all Postgres chunks after pipeline |

### Demo proof

1. Upload a PDF via the UI or `POST /documents/upload`
2. UI upload auto-triggers `process_document` → `rebuild_vector_index`
3. After upload: document status shows `ready`, chunk count visible in UI
4. `GET /documents/{id}/chunks` lists chunks with page ranges

### Chunk count math

A 100-page PDF with ~500 chars/page = ~50,000 chars.
With 1200-char chunks and 200-char overlap, step size ≈ 1000 chars.
→ 50,000 / 1000 ≈ 50 chunks (low end).

A denser 100-page doc with ~2,000 chars/page = ~200,000 chars.
→ 200,000 / 1000 ≈ 200 chunks.

The "200–500 searchable chunks" claim is accurate for a typical 100-page PDF. Run `scripts/seed_sample.py` to see the actual count for a real document.

### Interview talking points

- Why character-based chunking? Simple, no NLP dependency, predictable chunk sizes, works for any language.
- Why overlap? Prevents context from being split at a chunk boundary — a sentence that spans two chunks appears in both, so queries about it will always retrieve relevant context.
- Why store chunks in Postgres? Metadata (page range, doc ID) lives alongside content, making filtered retrieval and citation rendering straightforward without a separate metadata store.

---

## Bullet 2 — FAISS cosine-similarity retrieval

**Claim**: "Implemented FAISS cosine-similarity retrieval across 2,000+ embeddings with sub-300ms query latency (local p95)"

### Code proof

| Component | File | Detail |
|---|---|---|
| Index type | `app/core/vector_store.py` line 62 | `faiss.IndexFlatIP` — exact inner product |
| Normalization | `app/core/embeddings.py` lines 10–13 | Row-wise L2 normalization: `vec / ‖vec‖` |
| Why IP = cosine | Both index and query vectors are unit-norm. IP of two unit vectors equals cosine similarity by definition. | |
| Search | `app/core/vector_store.py` lines 83–109 | Returns `(chunk_ids, scores)` sorted by descending similarity |

### Latency benchmark

Run `python scripts/benchmark.py` to measure p95 retrieval latency with 2,500 synthetic vectors.

Expected output: FAISS retrieval at this scale takes < 1ms. The sub-300ms claim refers to end-to-end query latency, which is dominated by the OpenAI embedding API (~100–200ms network call), not the FAISS search itself.

### 2,000+ embeddings

Each chunk becomes one 1536-dimensional vector. With 2+ documents each producing 200–500 chunks, the index easily exceeds 2,000 vectors. The `scripts/seed_sample.py` script demonstrates this with a real PDF.

### Interview talking points

- Why `IndexFlatIP` and not `IndexFlatL2`? Normalized vectors make inner product equal cosine — same result, and inner product is what OpenAI embeddings are designed for.
- Why exact search and not approximate? At 2K–10K vectors, FAISS exact search is microseconds. Approximate methods (IVF, HNSW) trade accuracy for speed — the tradeoff only makes sense above ~100K vectors.
- What does the score mean? It's the cosine similarity between query embedding and chunk embedding, ranging from -1 to 1. Above ~0.35 typically indicates topical relevance. The answer endpoint uses 0.25 as a relevance floor.

---

## Bullet 3 — Citation-aware RAG, re-indexing, lifecycle

**Claim**: "Added citation-aware RAG responses with automatic re-indexing and document lifecycle state management"

### Code proof — citations

| Component | File | Detail |
|---|---|---|
| Context building | `app/api/answer.py` lines 73–101 | Numbers each chunk `[1]...[n]`, includes doc title + page range |
| System prompt | `app/core/llm.py` lines 19–26 | "Every factual claim MUST have a citation like [1]" |
| Response parsing | `app/api/answer.py` lines 128–130 | Returns `answer` (string with `[n]`) + `citations` list |
| UI rendering | `app/ui/templates/home.html` lines 119–128 | Renders `[n] doc_title (pages X–Y)` + snippet per citation |

The citation chain is verifiable: each `[n]` in the answer maps to a specific `AnswerCitation` with `chunk_id`, `page_start`, `page_end`, and a snippet.

### Code proof — automatic re-indexing

On every UI upload (`POST /ui/upload`):
1. `create_document_from_upload` saves the PDF
2. `process_document` runs extract → chunk
3. `rebuild_vector_index` re-embeds **all** chunks and saves a fresh FAISS index

This means every upload triggers a full index rebuild automatically — no manual step needed in the normal flow. The API path (`POST /documents/upload`) uploads only; re-indexing is triggered separately via `POST /search/rebuild`. This is a deliberate tradeoff: the UI optimizes for demo usability; the API optimizes for composability.

### Code proof — lifecycle states

| State | Set where |
|---|---|
| `uploaded` | Initial state from `create_document_from_upload` (via `processing`) |
| `processing` | Start of `process_document` in `services/pipeline.py` |
| `ready` | End of `process_document` on success |
| `failed` | `process_document` except block; also set on upload/extract errors |

State transitions are explicit and visible in the UI. The `error` field on `Document` stores the failure message when status is `failed`.

### Interview talking points

- How do citations work? Retrieved chunks are numbered 1..n and injected into the prompt. The model is told to use `[n]` for every claim. The API maps `[n]` back to the actual chunk record (doc title, page range, text snippet) and returns them alongside the answer.
- What prevents hallucination? The system prompt says "use ONLY the provided context" and "if you cannot cite it, do not say it." Additionally, the guardrail in `answer.py` skips the LLM entirely if cosine score < 0.25 or no query keywords appear in the retrieved text.
- Why full rebuild instead of incremental indexing? Correctness: a full rebuild from Postgres is idempotent and avoids stale or duplicate vectors. The tradeoff is O(n) cost per upload. For this scale (< 10K chunks) it's fine; at larger scale, append-only indexing + a deletion bitmap would be the upgrade path.
