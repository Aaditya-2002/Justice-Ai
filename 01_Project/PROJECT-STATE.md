# PROJECT-STATE.md — Current Implementation Snapshot

> **Single source of truth for project status.** Update after every meaningful change.

---

## Sprint Status

| Sprint | Status | Completion | Notes |
|--------|--------|------------|-------|
| Sprint 1: Foundation & Auth | ✅ **Complete** | 100% | All infrastructure, auth, tenant isolation, RAG basics |
| Sprint 2: LangGraph Orchestration | 📋 **Planned** | 0% | Awaiting Sprint 1 verification |
| Sprint 2: Provider-Agnostic LLM Integration | ✅ **Complete** | 100% | NVIDIA Build API + Gemini adapters, deterministic failover (cooldowns, deadlines, retries, secret redaction); **152/152 offline tests passing (exit 0)**; `nvidia_build` **VERIFIED LIVE** (2026-10-28), Gemini live **BLOCKED** (no `GEMINI_API_KEY`) |

---


## Operating Modes (Sprint 2)

### Current Mode: HYBRID (Mode A partial)
- `.env` sets `MODEL_PROVIDER_ORDER=nvidia_build,google`; `NVIDIA_API_KEY` is
  configured locally (never committed). `create_default_provider()` therefore
  returns a single `NVIDIABuildModelProvider` today and upgrades automatically
  to a `FailoverModelProvider` once `GEMINI_API_KEY` is also present.
- `nvidia_build` is **VERIFIED LIVE** (real `chat/completions`, 2026-10-28,
  model `nvidia/nemotron-3.5-lightning-30b-a3b`). Gemini live request is
  **BLOCKED** — no `GEMINI_API_KEY` available.
- Failover is **TESTED OFFLINE** with deterministic fakes (failover, cooldown,
  recovery, deadline, permanent-error short-circuit, secret hygiene) plus one
  scripted-failing-primary + real-NVIDIA-fallback run — that is NOT a
  two-real-provider live test.
- All 152 automated tests run offline (no network, no keys).
- RAG uses REAL sentence-transformers embeddings (all-MiniLM-L6-v2, 384-dim);
  MockEmbeddingProvider is only a fallback if model loading fails (verified 2026-10-28)
- Checkpointing NOT implemented (graph.compile() without checkpointer — single-turn execution only)
- Conversation resumption NOT implemented
- UniqueViolation test isolation issue: resolved
- NotImplementedError from aget_tuple: resolved (switched to async ainvoke + no checkpointer)

### Target Mode: NORMAL (Mode A) - Sprint 2 Goal
- `MODEL_PROVIDER_ORDER=nvidia_build,google` (failover chain) or a single real provider
- `NVIDIA_API_KEY` / `GEMINI_API_KEY` configured in environment
- Full LangGraph graph execution with external LLM
- Lightweight model integration (Qwen2.5-0.5B-Instruct Q4_K_M proposed, research documented in Obsidian)
- Streaming responses (Sprint 3)
- Real citation generation from external LLM
- Provider failover: implemented and offline-tested (cooldowns + deadlines); live rehearsal pending credentials

### Mode Transition Status
- [ ] Configure NVIDIA_API_KEY (nvapi-...) and/or GEMINI_API_KEY in .env
- [ ] Test Mode A execution with real providers (smoke tests pending credentials)
- [ ] Rehearse failover with a controlled primary-provider failure (live)
- [ ] Verify recovery from cooldown
- [ ] Mode A checkpointing compatibility verified

### Known Issues Affecting Mode Transition
- ISSUE-002: Real LLM Provider Not Configured (SECURITY.md)
  - Only `mock` provider implemented; NVIDIA Build API researched but not integrated
  - OpenAI/Anthropic not integrated
  - Target Fix: Sprint 2

## Verified Working (Evidence-Based)

### Infrastructure ✅
| Component | Verified | Evidence |
|-----------|----------|----------|
| PostgreSQL 18.6 | ✅ | `psql -c "SELECT version()"` returns 18.6 |
| pgvector extension | ✅ | `SELECT * FROM pg_extension WHERE extname='vector'` returns row |
| Database `justice_ai` | ✅ | Tables: users, tenants, conversations, messages, documents, document_chunks, alembic_version |
| Redis | ✅ | `redis-cli ping` → PONG |
| Alembic migrations | ✅ | `alembic upgrade head` succeeds, all tables created |

### Authentication & Multi-tenancy ✅
| Feature | Verified | Evidence |
|---------|----------|----------|
| JWT login endpoint | ✅ | `POST /api/auth/login` returns token with `tenant_id` |
| Token verification middleware | ✅ | Protected endpoints return 401 without valid token |
| ContextVar tenant isolation | ✅ | `tenant_id` extracted from JWT, scoped to request |
| RBAC permissions | ✅ | `users.permissions` comma-separated, enforced in skill registry |
| Default tenant | ✅ | Tenant `default` (id: `712dd85e-398d-4890-a030-07f811bc159f`) exists |

### Document Processing & RAG ✅
| Feature | Verified | Evidence |
|---------|----------|----------|
| Document upload | ✅ | `POST /api/documents/upload` stores file, extracts text |
| Text extraction | ✅ | PDF (PyPDF2), DOCX (python-docx), TXT |
| Chunking | ✅ | Configurable size/overlap, sentence-boundary aware |
| Embeddings | ✅ | `sentence-transformers` (all-MiniLM-L6-v2, 384-dim) |
| Vector storage | ✅ | `document_chunks.embedding` = `Vector(384)` (pgvector) |
| Similarity search | ✅ | Cosine similarity, top-k retrieval |
| Citation metadata | ✅ | Returns chunk, similarity, document_id, filename |
| Tenant-scoped queries | ✅ | All RAG queries filtered by `tenant_id` |

### Skill System ✅
| Feature | Verified | Evidence |
|---------|----------|----------|
| Skill registry | ✅ | Decorator-based registration, Pydantic I/O |
| `/skill` invocation | ✅ | ChatService parses `/skill name {json}` |
| Permission enforcement | ✅ | `required_permissions` checked at execution |
| Admin skill | ✅ | Requires `admin` permission, tests pass |

---

## Test Results (2026-10-20)

```
============================== 55 passed ==============================
tests/test_chat.py: 5 passed
tests/test_model_provider_config.py: 9 passed
tests/test_model_provider_contract.py: 11 passed
tests/test_model_provider_offline.py: 17 passed
tests/test_rag_service.py: 1 passed
tests/test_rag_verification.py: 5 passed
tests/test_skill_authorization.py: 3 passed
tests/test_skills.py: 5 passed
```

---

## Dependencies (Pinned in requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | 0.133.1 | API framework |
| uvicorn[standard] | 0.41.0 | ASGI server |
| sqlalchemy | 2.1.4 | ORM |
| pydantic | 2.13.4 | Validation |
| psycopg[binary] | 3.3.6 | PostgreSQL driver |
| pgvector | 0.5.1 | Vector type for SQLAlchemy |
| alembic | 1.13.1 | Migrations |
| pyjwt | 2.13.0 | JWT tokens |
| passlib | 1.7.4 | Password hashing |
| bcrypt | 3.2.0 | Bcrypt backend |
| python-jose | 3.3.0 | JWT utilities |
| sentence-transformers | 6.1.0 | Embeddings (all-MiniLM-L6-v2) |
| huggingface-hub | 1.24.0 | Model downloads |
| PyPDF2 | 3.0.1 | PDF text extraction |
| python-docx | 1.1.0 | DOCX text extraction |
| python-multipart | 0.0.32 | File uploads |
| python-dotenv | 1.2.2 | Env file loading |
| pytest | 9.1.1 | Testing |
| pytest-asyncio | 1.4.0 | Async test support |

---

## Known Issues / Blockers

| Issue | Severity | Status | Notes |
|-------|----------|--------|-------|
| Streaming responses not implemented | Medium | 📋 Sprint 2 | Required for token-by-token UI |
| Real LLM provider not configured | Low | 📋 Sprint 2 | Currently mock/sentence-transformers only |
| Frontend is legacy static files | Low | 📋 Sprint 2 | Needs React/Next.js rebuild |
| TestClient monkeypatch in test_chat.py | Low | ⚠️ Known | Workaround for FastAPI TestClient compat |
|| No GitHub Actions secrets configured | Medium | 🔧 Pending | Need to add DB/Redis service containers |

---

## Phase 1 Baseline — Repository State (Verified Against Source Code)

### Implemented and Tested (19/19 tests passing)

| Component | File | Status | Evidence |
|-----------|------|--------|----------|
| ModelProvider ABC | `app/core/model_provider.py` | IMPLEMENTED | `generate_response()`, `get_provider_name()`, `get_model_name()`, `health_check()`, `get_capabilities()` abstract methods |
| MockModelProvider | `app/core/model_provider.py` | IMPLEMENTED | Returns hardcoded response; dev/testing only; never a production fallback; capabilities explicitly all-False except chat_completions |
| ModelProviderFactory | `app/core/model_provider.py` | IMPLEMENTED | Only `"mock"` registered; raises `ValueError` otherwise |
| MODEL_PROVIDER config | `app/core/config.py` | CONFIGURED | `MODEL_PROVIDER="mock"`, `MODEL_NAME="mock-model"` |
| LangGraph orchestration | `app/orchestration/graph.py` | IMPLEMENTED | `graph.compile()` without checkpointer; `run_graph` async def + `await graph.ainvoke()` |
| Nodes | `app/orchestration/nodes.py` | IMPLEMENTED | 8 async nodes; router uses heuristic (not model-based) |
| Chat service | `app/services/chat_service.py` | IMPLEMENTED | Calls `run_graph()` with legacy fallback |
| RAG service | `app/services/rag_service.py` | IMPLEMENTED | Cosine similarity retrieval with pgvector |
| Embedding provider | `app/core/embedding_provider.py` | IMPLEMENTED | EmbeddingProvider ABC; MockEmbeddingProvider; SentenceTransformerEmbeddingProvider |
| Database | `app/core/database.py` | IMPLEMENTED | SQLAlchemy engine, SessionLocal, get_db() |
| Security/auth | `app/core/security.py` | IMPLEMENTED | JWT auth, ContextVar tenant isolation |
| Chat router | `app/routers/chat.py` | IMPLEMENTED | POST /api/v1/chat endpoint |
| Chat schema | `app/schemas/chat.py` | PARTIALLY IMPLEMENTED | FIXED — `citations: List[Dict[str, Any]] = []` added to ChatResponse |
| Tests | `tests/` | TESTED | 55/55 passing |

### Partially Implemented

| Component | File | Gap |
|-----------|------|-----|
| ChatResponse schema | `app/schemas/chat.py` | FIXED — `citations: List[Dict[str, Any]] = []` added |
| Router classification | `app/orchestration/nodes.py` | Calls ModelProviderFactory but ignores result; uses heuristic keyword matching instead |
| Provider configuration | `app/core/config.py` | Provider settings (MODEL_BASE_URL, MODEL_API_KEY, MODEL_TIMEOUT_SECONDS) are active with field validators |

### Missing Functionality

| Gap | Impact | Location |
|-----|--------|----------|
| No real LLM provider adapter | All generative LLM calls use MockModelProvider | `app/core/model_provider.py` |
| health_check() implemented | Provider health detection | `ModelProvider` ABC | ✅
| get_capabilities() implemented | Capability reporting | `ModelProvider` ABC | ✅
| No bounded retry logic | Unbounded retries on provider failure | `app/services/chat_service.py` |
| No provider-specific configuration | Cannot configure real provider | `app/core/config.py` |
| No provider contract tests | Cannot verify adapter compliance | `tests/` |
| Citations field added | Schema now includes citations field | `app/schemas/chat.py` | `app/schemas/chat.py` |

### Relevant Files Requiring Modification

| File | Required Change | Phase |
|------|----------------|-------|
| `app/core/model_provider.py` | Extend ABC with `health_check()` + `get_capabilities()`; update MockModelProvider | Phase 2 |
| `app/core/config.py` | Add provider settings (API key, base URL, timeout, retry settings) | Phase 3 |
| `.env.example` | Add provider configuration placeholders | Phase 3 |
| `app/services/chat_service.py` | Add bounded retries, timeouts, fallback handling | Phase 6 |
| `app/schemas/chat.py` | Add `citations` field to ChatResponse | Phase 5 |
| `app/orchestration/nodes.py` | Use model provider for classification (not heuristic) | Phase 5 |
| `tests/test_model_provider_contract.py` | New: provider contract tests (no credentials) | Phase 2 |
| `tests/test_model_provider_config.py` | New: configuration validation tests | Phase 3 |

### Recommended Implementation Sequence

| Order | Phase | Task | Dependency |
|-------|-------|------|------------|
| 1 | Phase 1 | Repository baseline — COMPLETE | None |
| 2 | Phase 2 | Extend ModelProvider ABC with `health_check()` + `get_capabilities()` | None |
| 3 | Phase 2 | Update MockModelProvider for new interface | Task 2 |
| 4 | Phase 2 | Write provider contract tests (offline, no credentials) | Tasks 2-3 |
| 5 | Phase 3 | Add provider configuration to config.py (.env.example placeholders) | None |
| 6 | Phase 3 | Add configuration validation tests | Task 5 |
| 7 | Phase 4 | Implement real provider adapter (blocked on provider selection) | Tasks 2-6 |
| 8 | Phase 5 | Fix ChatResponse schema to include citations | None |
| 9 | Phase 5 | Integrate provider into orchestration workflow | Tasks 2-8 |
| 10 | Phase 6 | Bounded retries, timeouts, fallback handling | Tasks 2-9 |
| 11 | Phase 7 | Security, privacy, observability | Tasks 2-10 |
| 12 | Phase 8 | Full test suite, release readiness | All above |
| 13 | Phase 9 | Documentation and Obsidian updates | All above |


---

## Recent Changes (2026-10-28b — live verification)

| Change | Files | Verification |
|---|---|---|
| LIVE: NVIDIA smoke test PASS — endpoint/auth verified, response `NVIDIA_OK`, isolated 3.87s / provider-path 7.74s | — | Against real `integrate.api.nvidia.com/v1` |
| LIVE: Gemini BLOCKED — no GEMINI_API_KEY provided | — | — |
| `meta/llama-3.3-70b-instruct` confirmed EOL (HTTP 410, EOL 2026-08-26). Default model changed to verified-live `nvidia/nemotron-3.5-lightning-30b-a3b` (from live /v1/models probe, 84 models listed) + tests updated | app/core/model_provider.py, tests/test_nvidia_provider_offline.py | Live generation succeeded |
| Defect fixes: `redact()` now scrubs any credential-shaped literal (nvapi-/sk-/AIza/ghp_/AKIA) even without the known secret; `_safe_error()` falls back to plain Exception for SDK classes with keyword-only ctor args (was masking real APIStatusError); HTTP 410/"end of life" now classified permanent (no futile retries) | app/core/model_provider.py | 144/144 tests pass, exit 0 |
| Failover semantics corrected: a SUCCESSFUL provider is no longer placed in cooldown (was: every success throttled the primary for MODEL_COOLDOWN_SECONDS, accidentally round-robining the chain); cooldown now = failure/deadline only. Tests updated to lock in first-healthy-wins + sticky primary | tests/test_failover_offline.py | Offline simulated failure → real-NVIDIA fallback served exact contract (prompt/history/RAG context preserved) |
| Config test isolation: tests now shield from a locally configured .env via `_env_file=None` / explicit init kwargs | tests/test_config_failover_offline.py, tests/test_model_provider_config.py | 144 passed |
| token.txt: prior commit did NOT include the staged deletion (still tracked in HEAD) — deletion re-staged, local copy preserved; committed in `2026-10-28c` | index | `D token.txt` staged |
| .env updated with NVIDIA_API_KEY + MODEL_PROVIDER_ORDER=nvidia_build,google only; all other settings preserved; key never displayed | .env | loaded + leak-scanned: NONE in repo files |

## Recent Changes (2026-10-28c — hardening commit & push)

| Change | Files | Verification |
|---|---|---|
| Committed and pushed the provider hardening work (redaction, `_safe_error`, 410 permanence, success-cooldown removal, verified-live NVIDIA default model) | app/core/model_provider.py, tests/*, README.md, 06_Deployment/DEPLOYMENT.md, 07_Knowledge/KNOWN-ISSUES.md, 01_Project/PROJECT-STATE.md | 152/152 offline tests pass, exit 0 |
| New regression coverage: credential-shape redaction (`redact`), 410/EOL permanence, bounded 429 retries, `_safe_error` keyword-only fallback, and conversation-history/skills preservation through failover | tests/test_redaction_offline.py, tests/test_provider_error_handling_offline.py, tests/test_failover_offline.py | 152 passed |
| token.txt untracked from the repository snapshot (expired JWT, local copy preserved). Earlier commits still contain it — no history rewrite, no force-push | index | Absent from latest snapshot; present in pre-`2026-10-28c` history |
| Docs honesty pass: NVIDIA = VERIFIED LIVE, Gemini = BLOCKED, failover = TESTED OFFLINE (one scripted-primary + real-NVIDIA run, not two real providers); stale `meta/llama-3.3-70b-instruct` references and 141-test counts updated | README.md, 06_Deployment/DEPLOYMENT.md, 07_Knowledge/KNOWN-ISSUES.md, 01_Project/PROJECT-STATE.md | Reviewed against code |
| Removed stray UTF-8 BOM accidentally introduced into tests/test_nvidia_provider_offline.py | tests/test_nvidia_provider_offline.py | File starts with `"""`, diff clean |

## Recent Changes (2026-10-28)

| Change | Files Modified | Verification |
|--------|----------------|--------------|
| Security: scrubbed expired JWT fragment (token.txt prefix) from docs; replaced with `<access_token>` / `<ACCESS_TOKEN>` placeholders | 03_Development/COMMANDS.md:174, 04_Database-API/API-CONTRACTS.md:24 | Fragment no longer matches any file; token.txt untracked (staged deletion) with local copy preserved |
| Capability fix: NVIDIA `meta/llama-3.3-70b-instruct` advertises `structured_output: False` per official model card ("Structured Output: Not supported") | app/core/model_provider.py, tests/test_nvidia_provider_offline.py | 141/141 tests pass (exit 0) |
| Credential check (2026-10-28): NVIDIA_API_KEY / GEMINI_API_KEY / MODEL_API_KEY not configured; live API tests deferred until keys are set | — | No secrets displayed during check |
| NOTE: token.txt JWT expired 2026-10-16; its first 36 chars remain recoverable from git history (4 commits). Rotation recommended; history purge optional | git history | token.txt JWT EXPIRED |

## Recent Changes (2026-10-20)

| Change | Files Modified | Verification |
|--------|----------------|--------------|
| Fixed psycopg/pgvector dependencies | requirements.txt | All tests pass |
| Added tenant_id to test users/conversations/messages | tests/*.py, chat_service.py | 19/19 tests pass |
| Fixed DocumentChunk chunk_metadata JSON serialization | rag_service.py | No more "cannot adapt type 'dict'" |
| Fixed delete_document to cascade delete chunks | document_service.py | FK constraints satisfied |
| Added tenant_id to Message creation | chat_service.py | NotNullViolation resolved |
| Updated requirements.txt with all deps | requirements.txt | Clean install works |

---

## Git Status

```
Branch: master
Remote: origin (https://github.com/Aaditya-2002/Justice-Ai.git)
Last commit: 40f1e65 "feat: Resolve LangGraph state validation, async execution, and citation integrity"
Working tree: MODIFIED (see below)
```

---

## Next Actions (Priority Order)

1. **~~Select primary LLM provider~~ DONE (2026-10-27):** `nvidia_build` + `google` (Gemini) adapters implemented with automatic failover; no credentials required to develop (`mock` remains default)
2. **~~Implement provider adapters~~ DONE (2026-10-27):** `OpenAICompatibleProvider` base + `NVIDIABuildModelProvider` + `GeminiModelProvider` in `app/core/model_provider.py`
3. **~~Register providers in factory~~ DONE (2026-10-27):** `ModelProviderFactory.create_provider()` + new `create_default_provider()` (MODEL_PROVIDER_ORDER chain or single provider)
4. **~~Bounded retries / health_check~~ DONE (2026-10-27):** exponential backoff, permanent-vs-transient error classification, secret redaction on every raised error
5. **~~Automatic failover~~ DONE (2026-10-27):** `FailoverModelProvider` — deterministic order, per-provider cooldowns, hard request deadline, `ProviderUnavailableError`
6. **Run benchmark protocol (V1-V5)** on target hardware before finalizing lightweight model
7. **Implement PostgresSaver** with tenant-scoped checkpoint namespace
8. **Add streaming support** to ChatService and frontend
9. Configure real credentials when ready: `NVIDIA_API_KEY` (nvapi-...) and/or `GEMINI_API_KEY`, then set `MODEL_PROVIDER_ORDER=nvidia_build,google`
10. Remove pre-existing DEBUG print statements (`app/orchestration/graph.py` lines ~154–171, `app/services/chat_service.py` lines ~100–106) — they echo request/response data to stdout

## LLM Integration Known Issues (Sprint 2)

| Issue | Severity | Status | Notes |
|-------|----------|--------|-------|
| Lightweight model not integrated | Medium | 📋 Planned | Qwen2.5-0.5B-Instruct Q4_K_M proposed; benchmarking required |
| External LLM API not configured | Medium | ✅ Code complete | NVIDIA Build API (`nvidia_build`) and Gemini (`google`) adapters + failover implemented; set `NVIDIA_API_KEY` (nvapi-...) and/or `GEMINI_API_KEY` to activate |
| Provider abstraction limited | Low | ✅ Resolved | `mock`, `nvidia_build`, `google` implemented; single or `MODEL_PROVIDER_ORDER` failover chain |
| Checkpointing not implemented | Low | 📋 Planned | graph.compile() without checkpointer; single-turn only |

---

## LLM Integration Research Status (Phase 2 — Complete)

Research documented in Obsidian vault (`C:\Obsidian\Hermes\Justice-AI-Research\`):

| Research Area | Status | Key Finding |
|--------------|--------|-------------|
| Lightweight model landscape | Complete | Qwen2.5-0.5B-Instruct Q4_K_M proposed (~280–386 MB, Apache 2.0) |
| Model source register | Complete | 22 sources for Qwen2.5-0.5B; 18 for Qwen2.5-Coder-0.5B; 14 for SmolLM2-360M |
| Evidence dossiers | Complete | Task suitability evaluated for 16 Justice AI roles |
| Artifact license audit | Complete | All shortlisted models: Apache 2.0 (commercial use permitted) |
| Architecture alternatives | Complete | Design F recommended (lightweight + NVIDIA Build API + fallback) |
| NVIDIA Build API research | Complete | Base URL: `https://integrate.api.nvidia.com/v1`; Auth: Bearer `nvapi-...` |
| Local inference feasibility | Complete | llama.cpp recommended; ~1 GB RAM for Qwen2.5-0.5B at 4K context |
| Security & legal reliability | Complete | Deterministic backend enforcement; DPDP Act review needed |
| Caching & concurrency | Complete | Tenant-scoped cache keys; bounded retries (max 3) |
| Capacity planning | Complete | Scenarios A–D defined; not benchmarked |
| Benchmark protocol | Complete | Test cases and pass/fail criteria defined |
| Provider portability baseline | Complete | ModelProvider ABC + MockModelProvider; no real provider integrated |
| Provider-agnostic architecture | Complete | Adapter pattern recommended; zero-code-change switching NOT achievable |
| Provider adapter research | Complete | Common capabilities, optional capabilities, unsupported-feature handling documented |
| Provider landscape | Complete | NVIDIA Build API, OpenAI, Google Gemini compared |
| Dynamic routing | Complete | Configuration-driven baseline; additional routing not justified for Phase 1-2 |
| Provider switching playbook | Complete | Migration steps, rollback triggers, testing checklist |
| Cost optimization | Complete | Free tier limitations; caching strategy; local model for supporting tasks |
| Failover and recovery | Complete | Circuit breaker, bounded retries, fallback disclosure |
| Security and privacy | Complete | DPDP Act review needed; NVIDIA data retention UNKNOWN |
| Caching, observability, metering | Complete | Tenant-scoped cache keys; no token metering implemented |
| Test plan | Complete | PT-01 through PT-32 defined |
| Decision report | Complete | 17 decisions; 5 require user input |

**Decision pending**: Primary LLM provider selection (requires user input on API credentials).
**Model selection pending**: Benchmarking on target hardware required before finalizing.

---

## Git Status