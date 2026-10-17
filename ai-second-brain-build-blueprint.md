# AI Second Brain — Portfolio MVP Build Blueprint

**Audience:** intermediate developer targeting AI engineering and full-stack internships  
**Schedule:** 12 focused days, about 3–5 hours/day (36–60 hours total)  
**Budget:** $0 for local development if OpenRouter's free model access is available; free access is rate-limited and can change. Deployed demo costs depend on hosting and persistent storage.  
**Product:** a private, single-user workspace for saving notes and PDFs, searching them, and asking questions with grounded answers and source citations.

## 1. Product scope

### MVP (finish these first)

- Dark dashboard with responsive sidebar, note list, search, and chat panel.
- Create, edit, delete, tag, and browse text notes.
- Upload text-based PDF files with a strict size limit; extract text and show page references.
- Chunk and embed notes/PDF pages; retrieve the most relevant chunks for a question.
- Ask questions over the user's own library. Return a concise answer, citations with source title and page/chunk, and an honest “I couldn't find that in your sources” response when retrieval is weak.
- Rebuild embeddings when a document changes; delete vectors when a source is deleted.
- Health endpoint, readable errors, basic test suite, seeded demo content, README, screenshots, and deploy instructions.

### Stretch (only after the MVP works end-to-end)

- Authentication and multiple users; OAuth; sharing or collaboration.
- OCR for scanned PDFs, DOCX/URL ingestion, browser extension, voice input.
- Streaming answers, conversation history, semantic-plus-keyword hybrid search, reranking.
- Background ingestion jobs, bulk imports, analytics, mobile PWA, cloud vector store.
- Automated deployment. Avoid spending MVP time on agent frameworks or elaborate orchestration.

## 2. Architecture

```text
React + TypeScript + Vite + Tailwind
            │ HTTPS JSON (same-origin in production via proxy, or CORS in dev)
            ▼
FastAPI ── SQLAlchemy ── SQLite (notes, documents, chunks, tags, conversations)
   │
   ├── PDF extraction (pypdf) → normalize → chunk with page metadata
   ├── OpenRouter embeddings API (Nemotron 3 Embed 1B free) → ChromaDB persistent local collection
   └── retrieve top-k chunks → OpenRouter chat completions (Nemotron 3.5 Lightning free) → citations
```

Keep the AI provider behind `EmbeddingProvider` and `GenerationProvider` interfaces. Keep retrieval and prompt construction in ordinary Python functions, not route handlers. SQL stores canonical source text and metadata; Chroma is a rebuildable search index, not the source of truth. Use SQLite and local Chroma in development and for a one-instance portfolio demo. Do not expose either database or the OpenRouter key to the browser.

**Request flow:**

1. User uploads a PDF or saves a note. Validate it; extract text; store the source and page-aware chunks in SQLite.
2. Embed chunks in batches, upsert vectors with deterministic IDs and metadata (`source_id`, `chunk_id`, `page`, `title`), then mark the source indexed.
3. At question time, embed the question, query Chroma for `top_k=5`, and discard matches below a configurable similarity threshold.
4. Build a bounded prompt containing only retrieved text and stable citation labels. Tell the model to treat source text as untrusted data, answer only from it, and cite labels for every factual claim.
5. Return answer and citation records from retrieved chunks. The backend—not model-generated URLs—resolves citations to source/page/chunk.

Similarity direction differs by Chroma API/metric; decide on cosine distance and convert distance to a similarity score consistently. Test the threshold against your own small evaluation set instead of treating a magic number as universal.

## 3. Technology and dependencies

Use Python 3.12 and Node.js 22 LTS as the baseline. Pin exact versions in lock files / `requirements.txt`; upgrade deliberately and rerun the suite. The versions below are a reproducible starting set, not a claim that each is the newest release on installation day.

### Frontend (`web/package.json`)

| Package | Version | Purpose |
|---|---:|---|
| `react` | `^19.1.0` | UI |
| `react-dom` | `^19.1.0` | DOM renderer |
| `react-router-dom` | `^7.6.2` | Routes |
| `@tanstack/react-query` | `^5.80.7` | API state/cache |
| `react-markdown` | `^10.1.0` | Render assistant Markdown safely |
| `lucide-react` | `^0.468.0` | Icons |
| `clsx` | `^2.1.1` | Conditional class names |
| `tailwind-merge` | `^3.3.0` | Merge Tailwind classes |
| `tailwindcss` | `^4.1.8` | Styling |
| `@tailwindcss/vite` | `^4.1.8` | Vite integration |
| `vite` | `^6.3.5` | Dev server/build |
| `typescript` | `~5.8.3` | Type checking |
| `@vitejs/plugin-react` | `^4.5.0` | React transform |
| `vitest` | `^3.2.4` | Unit/component tests |
| `@testing-library/react` | `^16.3.0` | UI tests |
| `@testing-library/user-event` | `^14.6.1` | Interaction tests |
| `@testing-library/jest-dom` | `^6.6.4` | DOM assertions |
| `jsdom` | `^26.1.0` | Browser-like test environment |
| `eslint` | `^9.28.0` | Lint |
| `typescript-eslint` | `^8.34.1` | TS lint rules |

Install `lucide-react` rather than importing an icon library through a CDN. Use native `fetch` or a small typed API wrapper; don't add Axios unless a real need appears. Use CSS variables for the design tokens; no component library is required for the premium look.

### Backend (`api/requirements.txt`)

```text
fastapi==0.115.12
uvicorn[standard]==0.34.3
sqlalchemy==2.0.41
alembic==1.16.1
pydantic-settings==2.9.1
python-multipart==0.0.20
pypdf==5.6.0
chromadb==1.0.12
openai==1.88.0
tenacity==9.1.2
pytest==8.4.0
httpx==0.28.1
ruff==0.11.13
```

FastAPI/Pydantic validate request and response shapes. `pypdf` extracts selectable text; it does not OCR image-only pages. Chroma persists locally under `CHROMA_PERSIST_DIR`. SQLAlchemy + Alembic keep schema changes reviewable. OpenRouter exposes OpenAI-compatible endpoints: use the `openai` Python package with `OpenAI(base_url="https://openrouter.ai/api/v1", api_key=...)`; call `chat.completions.create` for generation and `embeddings.create` for vectors. Use `nvidia/nemotron-3.5-lightning:free` for chat and `nvidia/nemotron-3-embed-1b:free` for embeddings. These are separate models: Lightning is not the embedding model. Confirm both slugs and availability on their OpenRouter model pages when you start, since free model availability and limits can change.

### Runtime configuration

Put model IDs behind environment variables: `OPENROUTER_CHAT_MODEL=nvidia/nemotron-3.5-lightning:free` and `OPENROUTER_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b:free`. Set `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`. The `:free` endpoint currently reports zero token price, but free endpoints are rate-limited, can be temporarily unavailable, and may be subject to account request/day limits; free access is not unlimited. The OpenRouter page for free Lightning states that using it consents to NVIDIA collection/recording/use under its API trial terms and says not to submit confidential or personal data. Use synthetic/public demo documents, and check the active provider's terms and privacy settings before sending real documents. Do not configure automatic fallback to a paid model. Keep output tokens and request volume bounded. The endpoint does not support enforced `response_format`, so validate model output in application code.

## 4. Folder structure

```text
ai-second-brain/
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml                 # optional local convenience; stretch
├── web/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/                       # router, query client, app shell
│   │   ├── components/                # sidebar, cards, dialogs, citations
│   │   ├── features/
│   │   │   ├── library/               # note list, filters, upload
│   │   │   ├── notes/                 # note editor and mutations
│   │   │   └── chat/                  # composer, messages, sources
│   │   ├── lib/api.ts                 # typed fetch, errors
│   │   ├── styles/                    # tokens.css, globals.css
│   │   └── test/
├── api/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/config.py             # settings, limits
│   │   ├── db/                         # engine, session, models
│   │   ├── schemas/                    # Pydantic DTOs
│   │   ├── api/routes/                # health, notes, documents, search, chat
│   │   ├── services/                  # CRUD, ingestion, retrieval, chat
│   │   ├── ai/                         # provider adapters, prompts
│   │   └── security/                   # upload validation, rate limits
│   └── tests/                          # unit, API, RAG evaluation
├── data/                               # gitignored local DB, Chroma, uploads
└── docs/
    ├── architecture.md
    └── screenshots/
```

## 5. Data model

Use UUIDs stored as strings for portable IDs, UTC timestamps, and foreign keys with cascade deletes. MVP is single-user; adding a `users` table later must add `user_id` ownership to every resource and filter every query by authenticated user.

| Table | Fields / constraints |
|---|---|
| `sources` | `id` PK; `kind` enum (`note`, `pdf`); `title`; `original_filename` nullable; `mime_type`; `size_bytes`; `content_sha256`; `status` (`pending`, `indexed`, `failed`); `error_message` nullable; `created_at`, `updated_at`; index on `(kind, updated_at)` |
| `chunks` | `id` PK; `source_id` FK cascade; `ordinal`; `page_number` nullable (1-based); `text`; `token_estimate`; unique `(source_id, ordinal)`; index on `source_id` |
| `tags` | `id` PK; `name` unique case-insensitive after normalization |
| `source_tags` | `source_id` FK cascade; `tag_id` FK cascade; composite PK |
| `conversations` | `id` PK; `title`; `created_at`, `updated_at` |
| `messages` | `id` PK; `conversation_id` FK cascade; `role` (`user`, `assistant`); `content`; `created_at`; `model_id` nullable; `retrieval_ids` JSON nullable; index `(conversation_id, created_at)` |

Don't store PDF binaries in SQLite. For the MVP, store uploaded PDFs under `data/uploads/{source_id}.pdf`, with the relative path derived by the server, not user input. Set an upload size cap (e.g. 10 MB), PDF page cap (e.g. 100), and extracted text cap. If a binary store is later added, store an opaque object key in a new field. SQLite and Chroma should be backed up together; embeddings can be regenerated from source/chunk text.

## 6. API contract

Prefix all business routes with `/api/v1`; keep `GET /health` as the simple unprefixed liveness route. Return Pydantic response models; use consistent errors `{ "detail": "...", "code": "..." }`. Paginate list/search results with `limit` and `cursor` or simple `offset` for the small MVP.

| Method + route | Purpose |
|---|---|
| `GET /health` | Liveness only: `{ "status": "ok" }` |
| `GET /api/v1/health/ready` | Check DB and vector store initialization without exposing secrets |
| `GET /api/v1/sources` | List notes/PDFs; optional `q`, `kind`, `tag`, `limit`, `offset` |
| `POST /api/v1/notes` | Create note `{title, content, tags[]}`; chunk and index |
| `GET /api/v1/sources/{id}` | Source metadata and safe content preview |
| `PATCH /api/v1/notes/{id}` | Update note; replace chunks and vectors transactionally or mark reindex needed |
| `DELETE /api/v1/sources/{id}` | Delete metadata, upload and all vector IDs; idempotent |
| `POST /api/v1/documents` | Multipart PDF upload; validate/extract/index; return source + indexing status |
| `GET /api/v1/sources/{id}/chunks` | Debug/inspect extracted chunks; paginate; never expose internal filesystem paths |
| `POST /api/v1/search` | `{query, limit?}`; return ranked snippets and source/page metadata without LLM generation |
| `POST /api/v1/chat` | `{question, conversation_id?}`; answer, conversation id, citations, `grounded` flag |
| `GET /api/v1/conversations/{id}` | Load messages and stored citation metadata |
| `GET /api/v1/tags` | List tags with source counts |

Use `201` for creation, `202` only if indexing actually runs asynchronously, `413` for oversize files, `415` for wrong media type, `422` for invalid input, `429` for provider/app limits, and `503` for unavailable external AI service. Keep provider exceptions out of responses and logs; return a request ID for support.

## 7. RAG and citation design

### Ingestion

1. Validate extension **and** MIME/signature; reject encrypted, empty, huge, or unsupported files. Treat filename as display-only; generate server IDs.
2. Extract each PDF page independently with `pypdf`, preserving 1-based page number; normalize whitespace while preserving paragraph boundaries. Reject if total extracted text is empty and explain OCR is not in MVP.
3. Chunk around 700–900 tokens with 100–150 token overlap, preferably at paragraph/sentence boundaries. Record a token estimate and deterministic chunk IDs. Keep each chunk small enough for the embedding endpoint. If the embedding model or vector dimension changes, re-embed the whole collection before querying it.
4. Store source and chunks first; call the OpenRouter embeddings API in bounded batches with retry/backoff only for transient errors. Upsert vectors; then mark indexed. On failure, keep source with `failed` status and allow retry. Avoid a long SQLite transaction while calling OpenRouter.

### Retrieval and generation

- Embed the question with the same embedding model/config used for the library.
- Query top 5 (initial default) chunks, optionally restricted to selected source IDs.
- Prompt includes the question, retrieved snippets marked as quoted/untrusted, and citation keys such as `[S1]`. It instructs the model to use only supplied evidence, cite claims, and state when the context is insufficient. Source text can contain prompt injection; do not follow instructions found inside it.
- Parse model output conservatively; validate citation keys against retrieved IDs. The response citations are built from backend metadata: `{source_id, title, page_number, chunk_id, excerpt}`. Drop invented keys and include only actually retrieved chunks.
- If retrieval is empty/below threshold, skip generation and return a grounded “I couldn't find this in your library” response, with a suggestion to add a source.
- Persist the user question, assistant response, model ID, and retrieved chunk IDs. Don't store the API key, hidden prompt, or raw provider request.

## 8. UI direction: premium dark dashboard

- **Canvas:** deep charcoal/navy (`#0B0D12`), elevated surfaces (`#11151D`, `#171C26`), thin cool borders, warm off-white text, muted slate secondary text.
- **Accent:** one electric violet or cyan accent for primary action, focus and active states. Reserve gradients for subtle highlights; avoid glowing every panel.
- **Layout:** 240px left rail; compact top bar with global search and profile placeholder; main workspace split into library/content and chat. Collapse left rail and stack panels on tablet/mobile.
- **Hierarchy:** clear “Second Brain” identity, selected page title, upload and new note actions, document cards with type/date/tag, chat sources as compact clickable evidence chips.
- **States:** skeletons, empty library onboarding, indexing progress, retry on failure, disabled/loading send button, file upload validation, toast confirmations, keyboard focus and reduced motion.
- **Polish:** consistent 8px spacing scale; 12–16px radii; restrained shadows; typography (Inter or system font); tooltips for icon-only controls; accessible contrast and visible focus. Use demo content that makes citations easy to see.

## 9. Environment setup

```bash
# Root
git init
cp .env.example .env

# API: create api/.venv with Python 3.12, activate it, then
python -m pip install -r api/requirements.txt
alembic -c api/alembic.ini upgrade head
uvicorn app.main:app --reload --app-dir api

# Web (Node 22 LTS)
cd web
npm install
npm run dev
```

Set Vite dev proxy `/api` → `http://127.0.0.1:8000` so the browser uses relative routes. Add `.env` and `.venv`, `web/node_modules`, `api/data`, SQLite files, PDFs, Chroma persistence, coverage/build output, and secrets to `.gitignore`.

`.env.example` (placeholders only):

```dotenv
APP_ENV=development
DATABASE_URL=sqlite:///./data/second_brain.db
CHROMA_PERSIST_DIR=./data/chroma
UPLOAD_DIR=./data/uploads
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=nvidia/nemotron-3.5-lightning:free
OPENROUTER_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b:free
FRONTEND_ORIGIN=http://localhost:5173
MAX_UPLOAD_MB=10
MAX_PDF_PAGES=100
MAX_CHAT_REQUESTS_PER_MINUTE=10
```

Create an OpenRouter API key in the OpenRouter dashboard and set it only in the backend environment. Keep `.env` out of Git. Add a startup config validation that gives a helpful error when AI is not configured; local CRUD/library features should still run, while chat/indexing returns a clear disabled/provider error. Never put `VITE_OPENROUTER_API_KEY` in frontend config. Do not enable paid model fallbacks if keeping the app strictly free.

## 10. Security, privacy, and reliability

- Treat MVP as a local single-user app; do not expose an unauthenticated public service containing private notes. For a public portfolio demo, seed public sample data and either keep ingestion private/local or add real authentication before handling other users' content.
- Restrict CORS to known origins; use HTTPS at deployment; never allow `*` with credentials. Keep API keys in host secret storage.
- Validate upload size, extension, MIME and PDF parse result; reject path traversal, encrypted PDFs, and excessive page/text counts. Don't render uploaded HTML or unsanitized Markdown as HTML.
- Rate-limit upload, indexing, and chat; cap prompt context, question length, output tokens and concurrency. Retry only transient 429/5xx with capped exponential backoff and jitter.
- Escape/quote retrieved content in the prompt and treat it as hostile; enforce citation validation in code. The model is not a security boundary.
- Avoid logging document text, prompts, API keys or personal data. Log request IDs, latency, token usage when provided, and provider status codes. Give users delete-all and source-delete paths.
- Free Nemotron endpoint use has provider-side data handling terms; use only synthetic/public demo material, not private notes or sensitive PDFs.
- Add basic CSRF protection if cookie auth is later introduced. Add authentication, ownership scoping, secrets rotation, retention policy and abuse controls before multi-user deployment.
- Add DB backups for a real persistent deployment; test a restore. Chroma is rebuildable only if canonical chunks remain available.

## 11. Test and quality plan

No live OpenRouter call in the regular test suite. Inject fake embed/generate adapters for deterministic API and RAG tests.

- **Backend unit:** chunk boundaries/overlap, page metadata, stable IDs, text normalization, filename safety, citation validation, empty/low-score retrieval, provider retry policy.
- **Backend API:** note CRUD; PDF accepted/rejected; failed indexing state; search returns source metadata; chat cites only retrieved chunks; delete clears DB and vector IDs; CORS and size limits.
- **Frontend:** note form validation, loading/error/empty states, upload progress, chat rendering, citation click opens correct source/page, keyboard navigation.
- **RAG mini-eval:** create 8–12 questions over 3 tiny fixture documents; include answerable and unanswerable cases. Track whether a relevant chunk appears in top 5, citation correctness, and unsupported-answer rate. Keep fixture PDFs synthetic/public-domain.
- **Release checks:** format/lint, typecheck, unit/API tests, build, manually verify narrow screen, no console/API errors, inspect Git diff for secrets and sample personal data.

Target: all critical CRUD and citation behavior deterministic in tests; document any known failure modes in README. Don't claim model accuracy from a handful of questions—present the mini-eval as a smoke test.

## 12. Twelve-day implementation schedule

| Day | Deliverable | Tasks / exit check |
|---|---|---|
| 1 | Scope, repo, visual shell | Create repo and README outline; scaffold Vite/FastAPI; define tokens and layout; API health works and dashboard renders. |
| 2 | Database + notes API | SQLAlchemy models/migration; create/list/get/update/delete notes; API tests; seeded examples. |
| 3 | Notes UX | Library list, editor, tags, empty/loading/error states; typed API client; note CRUD works end-to-end. |
| 4 | PDF ingestion | Upload validation, page extraction, status UI, source details; test text PDF and rejected cases. |
| 5 | Chunking + storage | Page-aware chunker, deterministic chunk IDs, DB transaction boundaries, retryable indexing status; unit tests. |
| 6 | Embeddings + vector search | Configure Nemotron 3 Embed 1B through OpenRouter; Chroma persistent collection; provider adapter and fake; search endpoint returns ranked citation metadata. |
| 7 | Grounded Q&A | Prompt assembly, answer endpoint, no-evidence fallback, citation validation, basic conversation persistence; mock tests. |
| 8 | Chat UI + polish | Chat panel, source chips/snippets, citation navigation; responsive dark dashboard; accessible focus and loading states. |
| 9 | Search + delete correctness | Library filters/search, reindex on edit, delete DB/file/vectors; idempotency and failure-path tests. |
| 10 | Security + quality | Limits, CORS, secret checks, rate limiting, logs, provider error handling; run suite and mini-eval. |
| 11 | Deployment + demo data | Deploy backend/frontend; configure secrets; persistent-storage decision; seed public synthetic dataset; verify demo from clean browser. |
| 12 | Portfolio finish | README architecture/setup/screenshots, known limits, evaluation notes; record short demo; fix top issues; tag v1.0. |

If time slips, drop tags, conversation history, and fancy animations before dropping citation correctness, PDF page metadata, deletion cleanup, tests, or deployment documentation.

## 13. Exact implementation order

1. Write acceptance criteria and seed examples before choosing visual details.
2. Scaffold app, configuration, and health checks.
3. Define schema and migrations; build CRUD with no AI dependency.
4. Build UI against CRUD and establish responsive design tokens.
5. Implement validated PDF extraction and source/chunk persistence.
6. Implement deterministic chunking and test page references.
7. Add provider interfaces and fake adapters; verify full ingestion/search path with fakes.
8. Add Nemotron embeddings through OpenRouter and Chroma upsert/query behind adapters.
9. Add grounded generation and citation validation; test no-evidence behavior.
10. Build chat UX and citation navigation.
11. Harden input limits, deletion, retries, secrets, logs, and rate limiting.
12. Add tests/eval, write docs, deploy with explicit storage behavior, capture screenshots.

## 14. Deployment choice and cost reality

For an internship portfolio, the best zero-cost path is often a local-run demo plus a hosted static frontend and an API demo backed by synthetic data. A free backend with SQLite/Chroma on local disk is **not durable**: Render documents that free web services use ephemeral storage and files are lost on restart/redeploy/spin-down. Its free Postgres has a 30-day expiry; persistent disks require paid service. OpenRouter currently lists 50 requests/day for its free plan; this can change and should be rechecked. Therefore:

- **$0 demo:** host static frontend and free API only for a disposable, public sample dataset; disclose cold starts and data reset. Keep uploads/ingestion disabled or seed on startup. Never promise persistence. Use only OpenRouter `:free` model slugs and disable paid fallbacks.
- **Durable personal demo:** use a service with persistent disk or managed database/vector storage and verify current price/limits before deployment. This can incur charges; set billing/spend caps. Chroma-on-disk and SQLite need a persistent volume and a single API instance.
- **Simplest reliable portfolio option:** don't host private uploads. Provide screenshots/video, a live public-data demo if a suitable free service is available, and one-command local setup. Recheck provider terms, account eligibility and current quotas on deployment day.

Render's current free tier is suitable for previews, but free web services spin down after 15 minutes idle and local changes are lost on restart/redeploy; free Postgres expires after 30 days. These facts can change, so check the live docs before choosing hosting. No named free tier should be treated as a permanent production guarantee.

## 15. README plan (portfolio-ready)

1. Project name, one-sentence value proposition, badges, live demo (if durable/usable), screenshot/GIF.
2. Problem and intended user; 4–6 MVP features.
3. Architecture diagram and RAG flow with citation example.
4. Tech stack with rationale: React/TS, FastAPI, SQLite, Chroma, OpenRouter (Nemotron chat + embedding models).
5. Local prerequisites, `.env` setup, migration, run commands, test commands.
6. Demo account/sample data instructions; explicit statement that no real user docs are bundled.
7. API summary and data model diagram/table.
8. Evaluation approach: synthetic questions, retrieval hit rate, citation checks, limitations.
9. Security/privacy: server-side secret, upload caps, single-user MVP, provider data terms, deployment persistence caveat.
10. Deployment architecture and cost assumptions; clearly mark any sleeping/ephemeral/free-tier services.
11. Screenshots (dashboard, PDF details, cited answer), short demo video, roadmap (stretch features).
12. Known limitations: OCR absent, PDF-only, no auth/multi-tenancy, model/quota can change, retrieval quality depends on source text.

## 16. Portfolio talking points

Be ready to explain why canonical content is in SQLite and vectors are rebuildable; how page metadata survives chunking; why citations are validated by the API; how prompt injection from retrieved documents is contained; what tests run without paid/live model calls; what changes before multi-user production; and how you measured retrieval quality. Those decisions demonstrate full-stack ownership and applied AI engineering beyond a chat UI.

## Sources checked (14 October 2026)

- OpenRouter's [Nemotron 3.5 Lightning free model page](https://openrouter.ai/nvidia/nemotron-3.5-lightning:free) lists the chat model slug, zero token price, rate limits, and NVIDIA's data-use warning for the free endpoint.
- OpenRouter's [Nemotron 3 Embed 1B free model page](https://openrouter.ai/nvidia/nemotron-3-embed-1b:free) documents the separate embeddings model and `/api/v1/embeddings` endpoint.
- OpenRouter's [Python/OpenAI-compatible integration docs](https://openrouter.ai/docs/community/frameworks) document the OpenAI SDK with `https://openrouter.ai/api/v1`.
- OpenRouter's [pricing and free plan](https://openrouter.ai/pricing/) documents current free-plan limits; check again when deploying.
- Render's [free instance documentation](https://render.com/docs/free) covers spin-down, ephemeral filesystems, and free Postgres expiry; its [disk docs](https://render.com/docs/disks) describe persistent disk limitations.
