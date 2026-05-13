# FinanceSight — Financial RAG Pipeline

> **Chat with SEC 10-K filings using a production-grade RAG pipeline built entirely from scratch.**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Mistral AI](https://img.shields.io/badge/Mistral_AI-API-FF7000?style=flat-square)](https://docs.mistral.ai)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

---

## What is FinanceSight?

FinanceSight is a **production-quality Retrieval-Augmented Generation (RAG) system** that lets financial analysts and investors ask natural language questions directly over SEC 10-K annual filings — and receive precise, cited, evidence-backed answers.

The entire pipeline — PDF ingestion, text chunking, vector search, BM25 keyword search, hybrid fusion, re-ranking, generation, hallucination filtering, and guardrails — is **built from scratch** with no RAG libraries, no vector database, and no search frameworks.

**Who is it for?**
- Financial analysts who need to extract data from hundreds of pages of SEC filings instantly
- Investors comparing financial metrics across companies and fiscal years
- Anyone who needs to query dense financial documents without reading them manually

---

## Knowledge Base

10 SEC 10-K annual filings from FAANG (excl. Netflix) + NVIDIA across FY2023 and FY2024:

| Company | FY2023 | FY2024 |
|---|---|---|
| Apple Inc. | ✅ | ✅ |
| Meta Platforms | ✅ | ✅ |
| Amazon.com | ✅ | ✅ |
| Alphabet Inc. (Google) | ✅ | ✅ |
| NVIDIA Corporation | ✅ (FY2024, ends Jan 2024) | ✅ (FY2025, ends Jan 2025) |

---

## Features

### Core Pipeline
- **PDF Ingestion** — multi-file upload, async background processing, 50 MB limit, magic-byte validation
- **Custom Chunking** — recursive delimiter-aware splitter (paragraph → sentence → word), 4096-char chunks, 400-char overlap
- **Batched Embeddings** — Mistral `mistral-embed` in batches of 32, 1024-dimensional vectors
- **Semantic Search** — cosine similarity over NumPy matrix (no vector DB)
- **BM25 Keyword Search** — Okapi BM25 implemented from scratch with precomputed TF maps
- **Hybrid Retrieval** — Reciprocal Rank Fusion (RRF, k=60) merging semantic + BM25 results
- **Re-ranking** — min-max normalized score fusion (0.7 × semantic + 0.3 × BM25)
- **Intent Detection** — classifies queries: conversational / factual / list / table / comparison
- **Query Transformation** — rewrites queries with financial terminology for better retrieval
- **Generation** — `mistral-large-latest` with per-intent prompt templates

### Bonus Features
- **Citations** — every answer includes inline `[N]` markers mapped to source chunks with page numbers
- **Insufficient Evidence** — refuses to answer when top-k similarity < 0.35 threshold; no hallucinated answers
- **Answer Shaping** — switches between paragraph, bullet list, markdown table, and comparison templates by intent
- **Hallucination Filter** — sentence-level embedding check; removes any sentence not grounded in source chunks
- **Guardrails** — PII detection (email, phone, SSN, credit card), prompt injection detection, investment advice refusal, medical disclaimer

### UI
- React + TypeScript frontend with Claude-inspired layout
- Sidebar document manager with upload, status tracking, and delete
- Dark mode toggle
- Inline citation chips — click to jump to source page in PDF viewer
- Toggleable split-pane PDF viewer with zoom + page navigation
- Draggable resize divider between chat and PDF panes
- Markdown rendering for structured answers (tables, lists)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FinanceSight                             │
│                                                                 │
│  ┌──────────────────┐          ┌─────────────────────────────┐ │
│  │  React Frontend  │◄────────►│      FastAPI Backend         │ │
│  │  (Vite + TS)     │  HTTP    │     (uvicorn, async)         │ │
│  └──────────────────┘          └─────────────────────────────┘ │
│                                          │                      │
│                          ┌───────────────┼───────────────┐     │
│                          ▼               ▼               ▼     │
│                    Mistral API      NumPy Store      PDF Files  │
│                  (embed + gen)    (in-memory +     (backend/    │
│                                   JSON persist)      pdfs/)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Ingestion Pipeline

```
POST /ingest (one or more PDF files)
       │
       ▼
┌─ Security Layer ───────────────────────────────────┐
│  • Extension + magic bytes validation (.pdf, %PDF)  │
│  • 50 MB per-file size limit                        │
│  • Filename sanitization (path traversal blocked)   │
└────────────────────────────────────────────────────┘
       │
       ▼  202 Accepted — background task starts
┌─ Text Extraction (PyMuPDF) ────────────────────────┐
│  • Page-by-page extraction                          │
│  • Text blocks only (images skipped, logged)        │
│  • Bounding box (bbox) captured per block           │
│  • Cumulative char offset tracked across pages      │
└────────────────────────────────────────────────────┘
       │
       ▼
┌─ Chunking (custom recursive splitter) ─────────────┐
│  • CHUNK_SIZE = 4096 chars (~1024 tokens)           │
│  • OVERLAP    = 400 chars  (~100 tokens)            │
│  • Split order: \n\n → .\n → . → space              │
│  • Guaranteed forward progress (no infinite loops)  │
│  • Each chunk: id, text, source, page, bbox, offset │
└────────────────────────────────────────────────────┘
       │
       ▼
┌─ Embedding (Mistral mistral-embed) ────────────────┐
│  • Batch size: 32 chunks per API call               │
│  • Output: 1024-dimensional float32 vectors         │
│  • Retry with exponential backoff (3 attempts)      │
└────────────────────────────────────────────────────┘
       │
       ▼
┌─ Vector Store ─────────────────────────────────────┐
│  • In-memory: List[Chunk] + NumPy float32 matrix    │
│  • Thread-safe with RLock                           │
│  • Atomic JSON persistence (write-tmp → replace)    │
│  • Auto-loaded from disk on server startup          │
│  • BM25 index rebuilt after every ingestion         │
└────────────────────────────────────────────────────┘
```

---

## Query Pipeline

```
POST /query { query, conversation_history }
       │
       ▼
┌─ Guardrails ───────────────────────────────────────┐
│  PII detected (email/phone/SSN/CC) → REFUSE         │
│  Prompt injection patterns         → REFUSE         │
│  Investment advice request         → REFUSE         │
│  Medical query                     → ALLOW + note   │
│  Empty query                       → REFUSE         │
└────────────────────────────────────────────────────┘
       │ allowed
       ▼
┌─ Intent Detection (mistral-small-latest) ──────────┐
│  conversational │ factual │ list │ table │ comparison│
│  temperature=0.0, max_tokens=32                     │
│  Few-shot examples in system prompt                 │
│  JSON output enforced, fallback to "factual"        │
└────────────────────────────────────────────────────┘
       │
       ├── conversational → generate directly (no retrieval)
       │
       ▼  (factual / list / table / comparison)
┌─ Query Transformation (mistral-small-latest) ──────┐
│  • Expand company names  (Apple → Apple Inc.)       │
│  • Expand abbreviations  (R&D, EPS, CapEx)          │
│  • Add SEC section names when relevant              │
│  • Decompose multi-part questions                   │
│  temperature=0.2, falls back to original on error   │
└────────────────────────────────────────────────────┘
       │
       ▼
┌─ Hybrid Retrieval ─────────────────────────────────┐
│                                                     │
│   Semantic Search          BM25 Keyword Search      │
│   ──────────────           ───────────────────      │
│   • Embed query            • Tokenize query         │
│   • Cosine similarity      • Okapi BM25 scoring     │
│     (NumPy dot product)      (K1=1.5, B=0.75)       │
│   • Top-20 results         • Top-20 results         │
│          │                        │                 │
│          └──────────┬─────────────┘                 │
│                     ▼                               │
│       Reciprocal Rank Fusion (RRF)                  │
│       score = Σ  1 / (60 + rank_i)                  │
└────────────────────────────────────────────────────┘
       │
       ▼
┌─ Re-ranking ───────────────────────────────────────┐
│  • Min-max normalize semantic scores → [0, 1]       │
│  • Min-max normalize BM25 scores    → [0, 1]        │
│  • Final = 0.7 × semantic + 0.3 × BM25              │
│  • Return top-8 chunks                              │
└────────────────────────────────────────────────────┘
       │
       ▼  best_score < 0.35?
┌─ Threshold Check ──────────────────────────────────┐
│  YES → return "insufficient evidence"               │
│        no LLM call, no hallucination risk           │
│  NO  → proceed to generation                        │
└────────────────────────────────────────────────────┘
       │
       ▼
┌─ Generation (mistral-large-latest) ────────────────┐
│  • System prompt selects template by intent         │
│  • Top-8 chunks injected as numbered context blocks │
│  • Conversation history (last 6 turns) included     │
│  • Inline [N] citation markers required by prompt   │
│  • Intent-specific max_tokens + temperature         │
└────────────────────────────────────────────────────┘
       │
       ▼
┌─ Hallucination Filter ─────────────────────────────┐
│  • Split answer into sentences                      │
│  • Embed each sentence (mistral-embed)              │
│  • Cosine similarity vs all source chunk embeddings │
│  • Sentence max_sim < 0.40 → removed from answer    │
│  • Fails open (API error → return original answer)  │
└────────────────────────────────────────────────────┘
       │
       ▼
{
  answer:               string,
  citations:            [{ id, source, page, text, bbox }],
  intent:               string,
  confidence:           number,
  disclaimer:           string | null,
  insufficient_evidence: boolean
}
```

---

## Chunking Strategy

> The task requires documenting chunking considerations — this section explains every decision.

### Chunk Size: 4096 characters (~1024 tokens)

SEC 10-K filings contain dense financial tables, multi-paragraph risk disclosures, and Management Discussion & Analysis sections where figures and their explanations often span full paragraphs. A chunk size of ~1024 tokens ensures:

- Full financial tables are captured intact (not split mid-row)
- Revenue discussions include both the figure and its surrounding context
- Each chunk is semantically self-contained enough to stand alone in retrieval

Smaller chunks (256–512 tokens) frequently split tables across boundaries — retrieving headers without values, or values without column headers — degrading retrieval quality significantly.

### Overlap: 400 characters (~100 tokens)

SEC filings regularly continue a financial figure's explanation across paragraph boundaries. The 400-character overlap ensures no critical sentence is lost between two adjacent chunks — particularly important for multi-part risk disclosures where conclusions span sections.

### Recursive Delimiter Priority

```
\n\n    →  paragraph break  (natural section boundary in SEC filings)
.\n     →  sentence at line end
.       →  inline sentence boundary
(space) →  word boundary (last resort — avoids mid-word splits)
```

The splitter tries the highest-priority delimiter first within the target window, respecting the document's natural semantic structure. SEC filings are organized into clear sections and paragraphs, so paragraph-level splits are preferred in almost all cases.

### No tiktoken

`tiktoken` is an OpenAI library and inconsistent with a Mistral-only stack. Character-based token estimation (÷4) removes an unnecessary dependency while remaining accurate enough for chunking purposes.

---

## Hybrid Retrieval Design

### Why hybrid over pure semantic search?

Semantic search excels at conceptual similarity but can miss exact financial terms. If a user asks about "EBITDA" or a specific revenue figure, BM25 keyword matching surfaces exact matches that embedding similarity might rank lower. Combining both gives the best of both worlds.

### Reciprocal Rank Fusion (RRF)

Rather than combining raw scores (which have incompatible scales), RRF merges ranked lists:

```
RRF_score(d) = Σ  1 / (k + rank_i(d))
```

Where `k=60` is the standard smoothing constant from the original literature (Cormack et al., SIGIR 2009). This is scale-invariant and robust to outliers in either ranking.

### Re-ranking

After RRF fusion, a weighted score gives semantic retrieval 70% weight vs BM25's 30%, reflecting that embedding similarity is more reliable for open-ended financial questions:

```
final_score = 0.7 × normalized_semantic + 0.3 × normalized_bm25
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Server health + chunk/document counts |
| `POST` | `/ingest` | Upload one or more PDF files for ingestion |
| `GET` | `/documents` | List all ingested documents with status |
| `DELETE` | `/documents/{filename}` | Remove a document from the knowledge base |
| `POST` | `/query` | Query the knowledge base with a user question |
| `GET` | `/pdfs/{filename}` | Serve raw PDF file to the frontend viewer |

### POST /ingest

```bash
curl -X POST http://localhost:8000/ingest \
  -F "files=@Apple_2023.pdf" \
  -F "files=@Apple_2024.pdf"
```

```json
{
  "files": [
    { "filename": "Apple_2023.pdf", "status": "accepted" },
    { "filename": "Apple_2024.pdf", "status": "accepted" }
  ]
}
```

Returns `202 Accepted` immediately. Ingestion runs in a background task — poll `GET /documents` to check status.

### POST /query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What were Apple'\''s total revenues in fiscal 2023?"}'
```

```json
{
  "answer": "Apple's total net sales for fiscal 2023 were $383.3 billion [1], a decrease from $394.3 billion in fiscal 2022 [2].",
  "citations": [
    { "id": 1, "source": "Apple_2023.pdf", "page": 32, "text": "...", "bbox": [72.0, 120.0, 540.0, 135.0] }
  ],
  "intent": "factual",
  "confidence": 0.87,
  "disclaimer": null,
  "insufficient_evidence": false
}
```

Full interactive API docs available at `http://localhost:8000/docs` (Swagger UI).

---

## Security

| Threat | Mitigation |
|---|---|
| Non-PDF file upload | Extension check + magic bytes (`%PDF`) validation |
| Oversized file upload | 50 MB hard limit enforced before writing to disk |
| Path traversal via filename | `Path(filename).name` strips all directory components |
| Secondary path traversal | `resolve().relative_to()` check before serving PDFs |
| API key exposure | `.env` file, gitignored — never hardcoded |
| Prompt injection | Regex pattern detection in guardrails before any LLM call |
| PII in queries | Email, phone, SSN, credit card regex → hard refuse |
| CORS | Explicitly locked to `localhost:5173` and `localhost:3000` |
| Concurrent ingestion race | `threading.Semaphore(1)` serializes ingestion tasks |
| Corrupt store on crash | Atomic write (write to `.tmp` → atomic replace) |

---

## Scalability

| Concern | Current (Demo) | Production Path |
|---|---|---|
| PDF ingestion blocking | FastAPI `BackgroundTasks` + semaphore | Celery + Redis task queue |
| Vector storage | NumPy matrix in memory + JSON on disk | pgvector or FAISS |
| Embedding API calls | Batched at 32 per call, sequential | Async parallel batches with rate limiting |
| Persistence | JSON file on disk | PostgreSQL |
| Concurrent queries | FastAPI async handlers | Horizontal scaling + load balancer |
| Large corpora | Single-process in-memory | Distributed vector store |

---

## Setup & Running

### Prerequisites

- Python 3.11+
- Node.js 18+
- Mistral AI API key — [get one at console.mistral.ai](https://console.mistral.ai)

### Backend

```bash
# 1. Clone the repo
git clone https://github.com/shivansh052k/FinanceSight.git
cd FinanceSight

# 2. Create and activate virtual environment
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Open .env and set: MISTRAL_API_KEY=your_key_here

# 5. Start the server
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`  
Interactive API docs at `http://localhost:8000/docs`

### Frontend

```bash
# From repo root
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

### Ingest PDFs

Once both servers are running, either:
- Click **Upload PDFs** in the sidebar and drag-and-drop your files, or
- POST directly to the API:

```bash
curl -X POST http://localhost:8000/ingest \
  -F "files=@backend/pdfs/Apple_2023.pdf"
```

Ingestion runs in the background. The sidebar status changes to **Ready** when complete.

---

## Example Queries

| Query | Intent | Behavior |
|---|---|---|
| `"Hello!"` | conversational | Responds naturally, no retrieval |
| `"What were Apple's total revenues in fiscal 2023?"` | factual | Cited single-figure answer |
| `"What risk factors did Meta highlight in their 2024 10-K?"` | list | Bulleted list with citations |
| `"Show NVIDIA's revenue breakdown by segment"` | table | Markdown table with citations |
| `"Compare gross margins across Apple and Google for 2023 and 2024"` | comparison | Cross-document structured comparison |
| `"Should I buy NVIDIA stock?"` | — | Refused: investment advice guardrail |
| `"My SSN is 123-45-6789, is this secure?"` | — | Refused: PII detected |
| `"What is the GDP of France?"` | factual | Insufficient evidence — not in filings |

---

## Repo Structure

```
FinanceSight/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI routes, CORS, lifespan
│   │   ├── ingestion.py       # PDF extraction + recursive chunking
│   │   ├── embeddings.py      # Mistral embed (batched, retry/backoff)
│   │   ├── vector_store.py    # Thread-safe store + atomic JSON persistence
│   │   ├── bm25.py            # Okapi BM25 from scratch
│   │   ├── retrieval.py       # Semantic + BM25 + RRF + re-ranking
│   │   ├── query_processor.py # Intent detection + query transformation
│   │   ├── generator.py       # Generation + intent-aware prompt templates
│   │   ├── hallucination.py   # Sentence-level embedding grounding check
│   │   └── guardrails.py      # PII, injection, investment, medical
│   ├── data/
│   │   └── vector_store.json  # Persisted embeddings (gitignored)
│   ├── pdfs/                  # Uploaded PDFs (gitignored)
│   ├── .env                   # API key (gitignored — never commit)
│   ├── .env.example           # Template — copy to .env and fill in key
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/        # ChatPane, MessageBubble, CitationChip,
│   │   │                      # PDFViewer, UploadModal, DocumentList
│   │   ├── hooks/             # useChat, useDocuments, usePDFViewer
│   │   ├── types/index.ts     # Shared TypeScript interfaces
│   │   ├── api/client.ts      # Axios API client
│   │   ├── App.tsx            # Layout + split-pane + dark mode
│   │   └── main.tsx
│   └── package.json
│
└── README.md
```

---

## Libraries & References

### Backend

| Library | Purpose | Link |
|---|---|---|
| FastAPI | API framework | [fastapi.tiangolo.com](https://fastapi.tiangolo.com) |
| uvicorn | ASGI server | [uvicorn.org](https://www.uvicorn.org) |
| PyMuPDF | PDF extraction + bbox metadata | [pymupdf.readthedocs.io](https://pymupdf.readthedocs.io) |
| NumPy | Cosine similarity math | [numpy.org](https://numpy.org) |
| mistralai | Embeddings + generation SDK | [github.com/mistralai/client-python](https://github.com/mistralai/client-python) |
| python-dotenv | `.env` loading | [github.com/theskumar/python-dotenv](https://github.com/theskumar/python-dotenv) |
| pydantic | Request/response validation | [docs.pydantic.dev](https://docs.pydantic.dev) |
| python-multipart | Multipart file upload support | [github.com/andrew-d/python-multipart](https://github.com/andrew-d/python-multipart) |

### Frontend

| Library | Purpose | Link |
|---|---|---|
| React 19 | UI framework | [react.dev](https://react.dev) |
| TypeScript | Type safety | [typescriptlang.org](https://www.typescriptlang.org) |
| Vite | Build tool | [vitejs.dev](https://vitejs.dev) |
| Tailwind CSS v4 | Styling | [tailwindcss.com](https://tailwindcss.com) |
| PDF.js | In-browser PDF rendering | [mozilla.github.io/pdf.js](https://mozilla.github.io/pdf.js) |
| Axios | HTTP client | [axios-http.com](https://axios-http.com) |
| react-markdown | Markdown rendering for LLM output | [github.com/remarkjs/react-markdown](https://github.com/remarkjs/react-markdown) |

### Algorithms & Research

| Reference | Link |
|---|---|
| Okapi BM25 (Robertson et al.) | [Wikipedia — Okapi BM25](https://en.wikipedia.org/wiki/Okapi_BM25) |
| Reciprocal Rank Fusion (Cormack et al., SIGIR 2009) | [plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) |
| Mistral AI Documentation | [docs.mistral.ai](https://docs.mistral.ai) |
| SEC EDGAR (source of all filings) | [sec.gov/cgi-bin/browse-edgar](https://www.sec.gov/cgi-bin/browse-edgar) |

---

## Limitations

- **In-memory store** — all embeddings loaded into RAM on startup. ~18,000 chunks across 10 filings ≈ 70 MB of float32 data. Scales to ~50 filings before memory becomes a concern.
- **JSON persistence** — fine for demo; not suitable for concurrent multi-process deployments.
- **No authentication** — API is open; suitable for local/demo use only.
- **Sequential ingestion** — the semaphore serializes uploads to avoid Mistral rate limits. Parallel ingestion would require async embedding with per-key rate limiting.
- **Scanned PDFs** — image-only PDFs produce no extractable text and will ingest as empty (logged as a warning, not silently swallowed).

---

*Built for the Stack AI Forward Deployed Engineer challenge — Task 3.*
