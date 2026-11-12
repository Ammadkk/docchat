# DocChat: Project Plan & Progress

> Chat with your PDFs. Upload documents, ask questions, and get answers with citations to the exact file and page.
> A free, local RAG (Retrieval-Augmented Generation) app: **Python (FastAPI) backend + React frontend**.

_Last updated: 2026-11-12_

---

## 1. Goals

- Upload PDFs, watch their ingestion status, and ask questions in a chat UI.
- Answers contain inline citations `[1]`. Each one maps to *filename, page N* and the exact source passage. Clicking a citation opens the PDF at that page with the passage highlighted.
- The app says **"I couldn't find that in your documents"** instead of making things up.
- An eval suite measures retrieval and answer quality, so improvements can be shown with numbers.
- **Everything is free.** No paid APIs, and everything runs on a laptop.

> **Why no Claude / OpenAI?** Those APIs are paid per token. This project uses **Ollama** (free, local open-source LLMs).
> The LLM sits behind a small interface (`backend/docchat/llm.py`), so a paid provider could be added later by implementing 3 methods. That is optional.

---

## 2. Tech stack (all free)

| Layer | Tool | Purpose |
|---|---|---|
| Language | Python 3.11+ (installed: 3.14) | Backend / AI |
| LLM | **Ollama** + `llama3.1:8b` (or `qwen2.5:7b`; `qwen2.5:3b` / `llama3.2:3b` on low-RAM PCs) | Answer generation, question rewriting, eval judge |
| Embeddings | `BAAI/bge-small-en-v1.5` on **ONNX Runtime** + `tokenizers` (no PyTorch). `sentence-transformers` is optional via `DOCCHAT_MODEL_BACKEND=torch` | Text → 384-dim vectors (CPU) |
| Vector DB | **ChromaDB** (persistent, local) | Similarity search with metadata filters |
| Keyword search | **rank_bm25** | Exact terms, names and numbers that embeddings miss |
| Reranker (optional) | `BAAI/bge-reranker-base` cross-encoder (ONNX) | Precision boost on top candidates |
| PDF parsing | **PyMuPDF** | Per-page text (keeps page numbers for citations) |
| Token counting | tiktoken | Token-aware chunking |
| API | **FastAPI** + Uvicorn | REST + Server-Sent Events streaming |
| Metadata DB | **SQLite** via SQLModel | Documents, conversations, messages |
| Frontend | **React 19 + Vite + TypeScript** | UI |
| Styling | **Tailwind CSS v4** + typography plugin, `lucide-react` icons | Modern look, dark mode |
| Data fetching | TanStack Query | Document list, status polling |
| Markdown | react-markdown + remark-gfm | Render answers |
| PDF viewer | **react-pdf** (pdf.js) | Show cited page, highlight passage |
| Upload | react-dropzone | Drag-and-drop |
| Tests / evals | pytest, custom eval script (LLM-as-judge via Ollama) | Quality |

No LangChain/LlamaIndex. The pipeline is hand-built so every part can be explained in an interview.

---

## 3. Architecture

```
            ┌──────────── INGESTION ────────────┐
PDF upload → save to data/uploads → PyMuPDF: text per page
          → chunk (~500 tokens, ~75 overlap, page numbers tracked)
          → embed with bge-small (passage side)
          → Chroma.add(vectors + metadata {doc_id, filename, page_start, page_end})
          → BM25 index marked dirty (rebuilt lazily on next query)

            ┌──────────── QUERY ────────────────┐
Question → (follow-ups) LLM rewrites into a standalone question using chat history
        → embed query (bge query-instruction prefix)
        → dense top-20 (Chroma)  +  BM25 top-20
        → Reciprocal Rank Fusion → [optional CrossEncoder rerank] → top 5
        → Guard 1: best similarity < threshold → "not found" (LLM not called)
        → prompt LLM with numbered sources [1]..[5]
        → stream tokens over SSE (Guard 2: hide the NOT_FOUND sentinel)
        → parse [n] citations, drop invalid ones, score claim↔source similarity
        → send sources {n, filename, pages, text, cited, support, low_confidence}
```

### Citations without a paid "native citations" API
1. Each retrieved chunk is numbered in the prompt: `[1] (report.pdf, p. 12) <text>`.
2. The system prompt requires a `[n]` after every factual sentence, or the exact reply `NOT_FOUND`.
3. A regex parses `[n]` and removes numbers that don't exist.
4. **Verification:** each cited sentence is embedded and compared to its cited chunk. Weak support (< 0.55) is flagged as *low confidence* in the UI.

### API contract

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/documents` | Upload PDF(s) (multipart `files`). Validates PDF, de-duplicates by SHA-256, ingests in the background |
| GET | `/api/documents` | List docs with status / pages / chunks |
| GET | `/api/documents/{id}` | One doc |
| GET | `/api/documents/{id}/file` | Serve the PDF (inline) for the viewer |
| DELETE | `/api/documents/{id}` | Remove file + vectors + row |
| POST | `/api/chat` | `{question, conversation_id?, doc_ids?}` → SSE events: `meta`, `token`…, `done` (answer + sources) or `error` |
| GET | `/api/conversations` / `/{id}` | Chat history |
| DELETE | `/api/conversations/{id}` | Delete chat |
| GET | `/api/health` | Ollama reachable? Model pulled? Chunks indexed |

---

## 4. Project structure

```
C:\docchat
├── PROJECT_PLAN.md            ← this file
├── .gitignore
├── data/                      (gitignored: uploads/, chroma/, docchat.db)
├── backend/
│   ├── .venv/                 (gitignored, dependencies installed)
│   ├── requirements.txt, pyproject.toml, .env.example
│   ├── main.py                FastAPI app, CORS, routers, /api/health, serves frontend/dist in prod
│   ├── db.py, models.py       SQLite engine + SQLModel tables (Document, Conversation, Message)
│   ├── ingest.py              PDF → chunks → embeddings → Chroma; resumes interrupted ingests
│   ├── cli.py                 Terminal test: `ingest <pdf>` / `ask "<question>"`
│   ├── routers/               documents.py, chat.py (SSE), conversations.py
│   ├── docchat/               ← RAG core (framework-free)
│   │   ├── config.py          all settings (env prefix DOCCHAT_)
│   │   ├── pdf_loader.py      per-page text extraction
│   │   ├── chunker.py         token-aware chunker with overlap + page tracking
│   │   ├── embeddings.py      bge embeddings (query vs passage), cosine; onnx/torch backend switch
│   │   ├── onnx_models.py     torch-free ONNX encoder + cross-encoder (HF onnx/model.onnx)
│   │   ├── vector_store.py    Chroma add / query / delete / filter by doc
│   │   ├── bm25_index.py      lazy BM25 keyword index
│   │   ├── retriever.py       hybrid search + RRF + optional rerank
│   │   ├── llm.py             LLM interface + Ollama implementation + health check
│   │   ├── prompts.py         answer / rewrite / judge prompts
│   │   ├── citations.py       parse, validate and support-score [n] citations
│   │   └── rag.py             full pipeline with streaming + not-found guards
│   ├── tests/                 test_chunker.py, test_retrieval_and_citations.py, test_rag.py
│   └── evals/                 run_evals.py, dataset.example.json
└── frontend/
    ├── package.json, tsconfig.json, vite.config.ts (proxy /api → :8000), index.html
    └── src/
        ├── main.tsx, index.css
        ├── api/client.ts      types, REST calls, SSE stream parser
        ├── hooks/useDocuments.ts, hooks/useChat.ts
        ├── lib/utils.ts
        ├── components/        Sidebar, UploadDropzone, DocumentList, ChatWindow, MessageBubble,
        │                      CitationChip, SourcesAccordion, PdfPanel (lazy-loaded), Toast, HealthBanner
        └── App.tsx            3-pane layout (sidebar | chat | PDF), mobile drawer
```

---

## 5. Progress

### ✅ Done

**Setup**
- [x] New standalone project at `C:\docchat` (separate from mortgage-crm), `git init` (branch `main`), `.gitignore`
- [x] Python venv created, **all backend dependencies installed** (torch, sentence-transformers, chromadb, pymupdf, fastapi, ollama, …)
- [x] Frontend dependencies installed (react 19, vite 8, tailwind 4, react-pdf 11, TanStack Query, react-markdown, react-dropzone, lucide-react, TypeScript 7)

**Backend: RAG core (`backend/docchat/`)**: all modules written
- [x] Config via env vars / `.env` (`.env.example` provided)
- [x] PDF loader (per page), chunker (token-aware, overlap, page tracking, hyphenation fix)
- [x] Embeddings (bge, query-instruction prefix, normalized vectors)
- [x] Chroma vector store (batched add, filtered query, delete by doc)
- [x] BM25 keyword index, hybrid retrieval with Reciprocal Rank Fusion, optional cross-encoder rerank
- [x] Ollama LLM wrapper (complete / stream / health)
- [x] Prompts (answer with `[n]` citations, follow-up rewrite, eval judge)
- [x] Citation parsing, validation, claim-support scoring
- [x] RAG pipeline: rewrite → retrieve → similarity guard → streamed answer with NOT_FOUND guard → sources

**Backend: API**: all modules written
- [x] SQLite models + engine, background ingestion, resume interrupted ingests on startup
- [x] Documents router (upload validation, 50 MB limit, SHA-256 dedupe, retry failed, serve file, delete)
- [x] Chat router (SSE streaming, conversation creation, history, saves answers + sources)
- [x] Conversations router, `/api/health`, CORS, production static serving of the React build
- [x] `cli.py` for terminal testing

**Quality**
- [x] Unit tests written: chunker (limits, pages, overlap), RRF, citation parsing, pipeline with fake LLM (streaming, NOT_FOUND hiding, similarity guard, follow-up rewrite)
- [x] Eval harness: hit@k + MRR for dense / hybrid / hybrid+rerank, LLM-judge correctness and faithfulness, citation-page accuracy, not-found accuracy → `evals/results.md`

**Frontend (partial)**
- [x] Vite + TS + Tailwind config, dev proxy to FastAPI, dark-mode bootstrap
- [x] `api/client.ts`: typed API + SSE parser
- [x] `hooks/useDocuments.ts`: list, status polling, upload/delete, "finished processing" callback
- [x] `hooks/useChat.ts`: streaming send, stop, new chat, load conversation
- [x] `lib/utils.ts`, `index.css` (highlight + streaming cursor styles)

**Step A: Backend verified (2026-11-12)**
- [x] `pytest`: 15 passed
- [x] **Smart App Control fix.** Windows Smart App Control (enforce mode) blocks unsigned DLLs: `torch.dll` and SQLAlchemy's Cython `.pyd` files. Two changes fixed it:
  - Embeddings and reranker now run on **ONNX Runtime** (Microsoft-signed) + `tokenizers`, using the official `onnx/model.onnx` from the BAAI repos. Same vectors (CLS pooling + L2 norm), no 2 GB PyTorch.
  - SQLAlchemy was reinstalled from its pure-Python `py3-none-any` wheel (steps in `requirements.txt`).
- [x] Real models checked: bge-small gives 384-dim normalised vectors (relevant 0.69 vs irrelevant 0.40). The reranker orders correctly.
- [x] Server smoke test: upload → `processing` → `ready` (2 pages, chunks > 0), `/file` serves the PDF, and `/api/health` reports Ollama status.
- [x] `/api/chat` SSE through the Vite proxy: an off-topic question returns "couldn't find" without calling the LLM. With Ollama down you get a friendly `error` event.

**Step B: React frontend done (2026-11-12)**
- [x] All components + `App.tsx` written. `npm run typecheck` is clean and `npm run build` succeeds.
- [x] The PDF viewer is lazy-loaded, which cuts the main bundle from 1.1 MB to 469 KB.
- [ ] The UI has not been checked visually in a browser with real answers yet. That needs Ollama.

### 🔲 Remaining work

**Step A2: Needs Ollama (you)**
1. Install Ollama (https://ollama.com/download), then `ollama pull llama3.1:8b` (or `qwen2.5:3b` if RAM < 16 GB). The Ollama installer is signed, so Smart App Control should allow it.
2. `python cli.py ingest some.pdf` then `python cli.py ask "..."`.
3. Run through the full UI flow in section 7.
4. Optional: the reranker downloads ~1.1 GB on first use (`DOCCHAT_USE_RERANKER=true`).

**Step C: Retrieval quality tuning**
- Tune `DOCCHAT_MIN_SIMILARITY` on real PDFs (too high gives false "not found", too low lets junk through)
- Try `DOCCHAT_USE_RERANKER=true`; compare chunk sizes 300 / 500 / 800

**Step D: Evals**
- Pick 3–4 public PDFs (e.g. a research paper, a product manual, an annual report)
- Write 30–50 questions in `backend/evals/dataset.json` (include ~5 unanswerable ones with `"expected_answer": "NOT_FOUND"`)
- `python -m evals.run_evals`, then put the results table in the README

**Step E: Polish & ship**
- Settings modal (model, top_k, reranker), keyboard shortcuts, mobile layout
- `README.md`: architecture diagram, screenshots / demo GIF, eval table, setup steps
- Optional `docker-compose.yml` (backend + Ollama + built frontend)
- First git commit, then push to GitHub

**Stretch (still free):** OCR for scanned PDFs (`ocrmypdf` / `pytesseract`), table extraction, multi-document compare mode, hosted demo via a free LLM tier (Groq / Gemini) behind `llm.py`.

---

## 6. How to run (once Step A/B are done)

```powershell
# 1. LLM
ollama pull llama3.1:8b

# 2. Backend  (terminal 1)
cd C:\docchat\backend
.venv\Scripts\activate
copy .env.example .env        # optional tweaks
uvicorn main:app --reload     # http://localhost:8000/docs

# 3. Frontend (terminal 2)
cd C:\docchat\frontend
npm run dev                   # http://localhost:5173
```

Production-style (single process): `npm run build` in `frontend`, then FastAPI serves `frontend/dist` at http://localhost:8000.

---

## 7. Verification checklist (definition of done)

- [x] `pytest` passes
- [ ] `/api/health` shows `llm_ok: true`
- [x] Upload a PDF → status goes `processing` → `ready`, and the chunk count is > 0
- [ ] Ask a question whose answer is on a known page → the citation shows that file and page, and the highlighted passage contains the answer
- [ ] A follow-up question ("what about the second one?") is answered correctly (rewrite works)
- [x] An off-topic question → "I couldn't find that in your documents." (similarity guard, verified without the LLM)
- [ ] Doc filter limits answers to the selected PDFs
- [ ] `python -m evals.run_evals` produces `evals/results.md`
- [ ] README with demo GIF and eval table

---

## 8. Interview talking points

Chunking trade-offs (size vs. overlap), asymmetric query/passage embeddings, approximate nearest-neighbour search (HNSW in Chroma), why hybrid search beats dense-only, Reciprocal Rank Fusion, cross-encoder reranking, grounded prompting, hallucination guards, citation verification, streaming UX via SSE, and measuring all of it with evals.
