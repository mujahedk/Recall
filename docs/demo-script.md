# Recall — Demo Script

A 2-minute walkthrough for live interviews and portfolio demos.

The fixture PDF is **"Attention Is All You Need"** (Vaswani et al., 2017) — a 15-page paper already committed to `fixtures/sample.pdf`. All curated questions below are verified to be answerable from it.

---

## Prerequisites

- Docker Desktop running
- `python3.12` installed (`brew install python@3.12`)
- `.env` present with `OPENAI_API_KEY` and `DATABASE_URL`

---

## One-time setup

```bash
make install       # creates .venv with python3.12, installs all deps
make db            # starts Postgres 16 in Docker
make migrate       # runs Alembic migrations
```

---

## Start the server

```bash
# Terminal 1 — keep this running
make dev
# → http://localhost:8000
```

---

## Load sample data (in a second terminal)

```bash
# Terminal 2
make demo          # = make reset + make seed
# Ingests fixtures/sample.pdf through the full pipeline:
#   parse PDF → extract pages → chunk text → embed → build FAISS index
```

Once seeding finishes the dashboard shows:
- 1 document with status **ready**
- Page count and chunk count
- Index status: **✓ Index ready — N vectors**

---

## 2-minute demo flow

### Step 1 — Open the dashboard (30 s)

```
http://localhost:8000
```

Point out:
- Document card with status badge ("ready"), page count, chunk count
- "Index ready — N vectors" confirms FAISS is loaded
- Two tabs: **Ask** (RAG) and **Search** (raw retrieval)

---

### Step 2 — Raw semantic search (30 s)

Click the **Search** tab. Enter:

> **How does multi-head attention work?**

Show the interviewer:
- Top-k chunks returned from FAISS
- Cosine similarity score next to each result (e.g. `score: 0.842`)
- Each result shows page number and source document

**What to say:** *"This is pure retrieval — no generation yet. FAISS does a dot-product over L2-normalised embeddings, which is equivalent to cosine similarity. These scores tell me how semantically close each chunk is to the query."*

---

### Step 3 — Citation-aware RAG answer (45 s)

Click the **Ask** tab. Enter the same question:

> **How does multi-head attention work?**

Show:
- A natural-language answer synthesised from the retrieved chunks
- Citations below the answer (document name + page number)
- The model is constrained to cite only what it retrieved — it cannot hallucinate sources

**What to say:** *"The system retrieves the top-k chunks first, then passes them to GPT as context. The prompt instructs the model to cite every claim using the chunk metadata I inject. If the answer isn't in the document, it says so."*

---

### Step 4 — Additional demo questions (optional, 15 s each)

| Question | What it demonstrates |
|---|---|
| `What is the Transformer model?` | Broad architectural question, tests coverage |
| `What BLEU score did the model achieve on WMT 2014 English-to-German?` | Precise factual retrieval with a numeric answer |
| `What are the encoder and decoder made of?` | Multi-citation answer across several sections |
| `What are the limitations mentioned in the paper?` | Tests whether the model stays grounded |

---

### Step 5 — Live benchmark (optional)

```bash
# Terminal 2
make benchmark
```

Shows p50/p95/p99 latency across 2,500 synthetic vectors. Use this to back up the sub-300ms resume claim on the spot.

---

## Reset for a clean demo

```bash
make reset    # wipes DB rows, storage files, and FAISS index
make demo     # re-seeds from fixtures/sample.pdf
```

---

## Interview Q&A cheat sheet

**Q: How does ingestion work?**
> PyMuPDF extracts text page-by-page. Each page is saved as JSON, then split into character-window chunks with overlap. Each chunk is embedded via OpenAI `text-embedding-3-small` and added to a FAISS `IndexFlatIP` index. Status transitions: `uploaded → processing → ready`.

**Q: How does retrieval work?**
> The query is embedded with the same model. FAISS computes inner products over L2-normalised vectors (= cosine similarity). Top-k chunks are returned with their scores.

**Q: Why FAISS instead of a vector database?**
> At thousands of vectors, FAISS `IndexFlatIP` loads in under 10ms and needs no external service. The trade-off is that it lives on disk and doesn't support live updates without a rebuild — acceptable for a document ingestion use case where re-indexing is triggered explicitly.

**Q: How do you prevent hallucination in citations?**
> The system prompt tells the model to cite only from the provided chunks using their metadata. It cannot fabricate a page number or document name that wasn't injected.

**Q: What happens when a new document is uploaded?**
> The pipeline runs synchronously: extract → chunk → embed → FAISS rebuild. The `DocumentStatus` field tracks each stage. If any step fails, the status is set to `failed` with an error message stored on the row.

**Q: What are the known limitations?**
> Synchronous ingestion blocks the request thread for large PDFs. No authentication. FAISS index is not persisted across container restarts unless the `storage/` volume is mounted. These are straightforward to address with a task queue and persistent volume.
