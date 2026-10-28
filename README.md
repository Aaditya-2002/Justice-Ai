# Justice AI — Multi-Tenant Legal AI Assistant (Backend)

Justice AI is a FastAPI backend for a **legal AI assistant** with multi-tenant
isolation, document upload and retrieval-augmented generation (RAG), skill
invocation, LangGraph orchestration, and pluggable LLM providers (NVIDIA Build
API and Google Gemini) with automatic failover.

> Status: **development-ready backend** — Sprint 1 (foundation & auth) and the
> LLM-provider integration (Sprint "Provider-Agnostic LLM Integration") are
> complete and covered by offline tests. The NVIDIA Build API provider is
> **VERIFIED LIVE** (real request, 2026-10-28). Gemini live verification is
> **BLOCKED** — no `GEMINI_API_KEY` is available yet. See
> [Known limitations](#known-limitations).

---

## Current features

| Feature | Status |
|---|---|
| Multi-tenant data model (every table scoped by `tenant_id`) | ✅ IMPLEMENTED |
| JWT authentication with tenant claims; request-scoped tenant isolation via `ContextVar` | ✅ IMPLEMENTED |
| RBAC (comma-separated permission strings) + skill authorization | ✅ IMPLEMENTED |
| Document upload (`.txt`, `.pdf`, `.docx`), text extraction, chunking | ✅ IMPLEMENTED |
| RAG: real `sentence-transformers` embeddings (`all-MiniLM-L6-v2`, 384-dim) stored with pgvector `Vector(384)` | ✅ IMPLEMENTED, TESTED OFFLINE |
| Similarity search + response pipeline with citations | ✅ IMPLEMENTED, TESTED OFFLINE |
| LLM providers: `nvidia_build` (NVIDIA Build API), `google` (Gemini via its OpenAI-compatibility endpoint) | ✅ IMPLEMENTED — `nvidia_build` **VERIFIED LIVE**, `google` live **BLOCKED** (no key) |
| Automatic provider failover: deterministic order, cooldowns, hard deadlines, bounded retries, secret redaction | ✅ IMPLEMENTED, TESTED OFFLINE |
| `mock` provider for offline development (never presented as real AI output) | ✅ IMPLEMENTED |
| Live smoke tests against NVIDIA / Gemini | NVIDIA ✅ **VERIFIED LIVE** (2026-10-28); Gemini ⛔ **BLOCKED** (no `GEMINI_API_KEY`) |
| Streaming responses | ❌ NOT IMPLEMENTED |
| LangGraph checkpoint persistence (multi-turn resume) | ❌ NOT IMPLEMENTED |
| `openai` (OpenAI direct) provider | ❌ NOT IMPLEMENTED |
| Frontend | ❌ legacy static pages only |

---

## Architecture

```
app/
├── main.py                 FastAPI app, routers
├── routers/                auth.py, chat.py, conversations.py, documents.py
├── services/               chat_service, document_service, rag_service,
│                           conversation_service, auth_service
├── orchestration/          LangGraph graph: validate → route → retrieve →
│                           skills → generate (nodes.py, state.py, graph.py)
├── skills/                 registry of skills with required permissions
├── models/                 SQLAlchemy models (User, Tenant, Conversation,
│                           Message, Document, DocumentChunk[Vector(384)])
├── schemas/                pydantic request/response models
└── core/
    ├── config.py           pydantic-settings (loads .env)
    ├── database.py         SQLAlchemy engine/session
    ├── security.py         JWT helpers
    ├── model_provider.py   MockModelProvider + OpenAICompatibleProvider base +
    │                       NVIDIABuildModelProvider + GeminiModelProvider +
    │                       FailoverModelProvider + ModelProviderFactory
    └── embedding_provider.py  sentence-transformers with mock fallback
tests/                      144 offline tests (pytest)
alembic/                    database migrations
frontend/                   legacy static pages (not maintained)
docs/…, 01–07_*/            project documentation
```

**Key services** (see `AGENTS.md`): `ChatService`, `DocumentService`,
`RAGService`, `ConversationService`, `AuthService`.

---

## Prerequisites

- **Python 3.14** (Windows path names below; equivalent on Linux/macOS)
- **PostgreSQL** with the **pgvector** extension (defaults to
  `127.0.0.1:5432`, database `justice_ai`)

> **Note:** there is no Redis dependency in the application code; older docs
> that mention starting a Redis server are outdated.

## Python environment

```powershell
cd "C:\Ai Agents\Justice AI"
python -m venv .venv             # the repo ships none; create fresh
.\.venv\Scripts\activate         # Windows PowerShell
```

## Dependency installation

```powershell
pip install -r requirements.txt
```

`requirements.txt` is pinned and verified: `pip check` reports no broken
requirements. Key pins: `fastapi==0.133.1`, `sqlalchemy==2.1.4`,
`pgvector==0.5.1`, `psycopg[binary]==3.3.6`, `openai==3.35.1`,
`langchain-openai==1.7.2`, `langgraph==1.2.18`,
`sentence-transformers==6.1.0`, `pytest==9.1.1`.

## PostgreSQL configuration

1. Create the database and enable pgvector:
   ```sql
   CREATE DATABASE justice_ai;
   -- then, inside justice_ai:
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
2. Set `DATABASE_URL` in `.env` (see below).
3. Apply migrations:
   ```powershell
   alembic upgrade head
   ```

Migrations are managed by Alembic (`tenant_id` columns and LangGraph
checkpoint tables included). Do not edit applied migration files.

## .env configuration

Copy the template and fill real values:

```powershell
Copy-Item .env.example .env
```

Placeholders only are committed (`.env` itself is gitignored). Full variable
reference lives in [`.env.example`](.env.example). Required for app startup:
`SECRET_KEY`. Recommended: `DATABASE_URL`.

## LLM provider setup

All providers speak the OpenAI Chat Completions wire protocol.

### NVIDIA Build API (`nvidia_build`)
- Get a key at [build.nvidia.com](https://build.nvidia.com) — keys start
  with `nvapi-` (enforced by the adapter).
- Default model: `nvidia/nemotron-3.5-lightning-30b-a3b` (verified live on
  2026-10-28 via `/v1/models` and a smoke generation). Structured output is
  reported as **not supported** by the adapter (conservative capability flag).
- **Deprecation watch:** NVIDIA deprecates model ids regularly — the previous
  default `meta/llama-3.3-70b-instruct` reached end of life on 2026-08-26 and
  now returns **HTTP 410**. HTTP 410 is treated as a permanent error (no
  retries). Check [models](https://build.nvidia.com/models) and override with
  `NVIDIA_MODEL_NAME` if needed.

### Google Gemini (`google`)
- Get a key at [Google AI Studio](https://aistudio.google.com/apikey).
- Uses the OpenAI-compatibility endpoint
  `https://generativelanguage.googleapis.com/v1beta/openai/`.
- Default model: `gemini-3.8-flash`.

### Provider order, failover, cooldown, timeouts

```properties
MODEL_PROVIDER_ORDER=nvidia_build,google
MODEL_COOLDOWN_SECONDS=60        # failed provider is skipped this long
MODEL_REQUEST_DEADLINE_SECONDS=60  # hard deadline per provider attempt
```

- Selection is **deterministic**: the first healthy provider in
  `MODEL_PROVIDER_ORDER` (candidates need their API key set) wins; without an
  order the single `MODEL_PROVIDER` is used; with nothing configured you get
  `mock`.
- On failure or deadline breach the provider is put into cooldown and the
  chain moves to the next candidate. Per-provider internal retries use
  exponential backoff (`MODEL_MAX_RETRIES`, `MODEL_RETRY_DELAY_SECONDS`;
  permanent errors like 401/404 fail fast).
- API keys are **redacted from every exception message** raised through the
  provider layer and from `ProviderUnavailableError` causes.
- A `mock` fallback never silently replaces a real provider in the chain:
  mock is only chosen when no real provider is configured.

## Running the backend

```powershell
uvicorn app.main:app --reload
```

API surface (JWT `Authorization: Bearer <token>` required):

- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`
- `POST /api/v1/chat`
- `POST /api/v1/documents` (multipart upload), `GET /api/v1/documents`, `GET /api/v1/documents/{id}`, `DELETE /api/v1/documents/{id}`
- `POST/GET /api/v1/conversations`, `GET/PATCH/DELETE /api/v1/conversations/{id}`

## Running tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q --tb=short
```

- **144 tests, all offline** (fixtures/fakes; no network, no API keys).
  Latest runs: `144 passed` in ~2:40, exit code 0.
- Live provider tests are **not automated**; after configuring keys, smoke
  test with minimal prompts and never send confidential legal or personal
  data to remote APIs.
- Live status: NVIDIA Build API **VERIFIED LIVE** (2026-10-28, real
  `chat/completions` request returning the expected token); Gemini **BLOCKED**
  (no key configured). Failover has been exercised offline with deterministic
  fakes and once with a scripted failing primary + real NVIDIA fallback — that
  is **not** a two-real-provider live test.

## Security considerations

- **Secrets**: `.env` is gitignored; API keys never appear in logs or raised
  errors (redaction in the provider layer). Never commit `.env`, tokens, or
  database dumps.
- **Tokens**: a documentation file previously contained an expired JWT
  fragment; it has been scrubbed. `token.txt` (an expired test JWT) is now
  **untracked** and absent from the latest snapshot, and `.env` stays
  gitignored. That expired token remains recoverable from earlier git history
  (no history rewrite was performed); it is expired and not tied to a live
  session.
- **Multi-tenancy**: all queries are tenant-scoped; skills enforce declared
  permissions at execution time.
- **Fallback disclosure**: in `mock` mode responses are explicitly produced
  by `MockModelProvider` (`"This is a mock response."`) and mock is never
  used as a silent production fallback.
- Upload payload size is capped (`MAX_UPLOAD_SIZE`, default 10 MB).

## Known limitations and remaining work

- **No streaming** responses; no multi-turn checkpoint persistence
  (LangGraph `compile()` has no checkpointer — single-turn execution).
- `openai` (OpenAI direct) provider raises `ValueError` by design
  (not implemented yet).
- Pre-existing `DEBUG: …` print statements in `app/orchestration/graph.py`
  and `app/services/chat_service.py` echo request/response data to stdout —
  remove before production.
- **NVIDIA model deprecation risk** — see above; verify model ids before use.
- Frontend is legacy static files (needs rebuild).
- No benchmark protocol (V1–V5) has been run for lightweight local models.
- Data protection review (DPDP Act) pending for real deployments.
- Git history contains an **expired** JWT (see Security); rotate any token
  that was issued with the same signing secret if in doubt.

## Documentation index

- `01_Project/PROJECT.md`, `PROJECT-STATE.md` — scope, current state
- `02_Architecture/ARCHITECTURE.md` — design
- `03_Development/COMMANDS.md` — dev cheat-sheet
- `04_Database-API/API-CONTRACTS.md` — API/data contracts
- `05_Security-Testing/` — security & testing docs
- `06_Deployment/DEPLOYMENT.md` — deployment notes
- `AGENTS.md` — coding-agent instructions (required reading)
