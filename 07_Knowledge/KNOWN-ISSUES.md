# KNOWN-ISSUES.md — Known Issues & Limitations

## Active Issues

### ISSUE-001: Streaming Responses Not Implemented
- **Severity**: Medium
- **Component**: ChatService, Frontend
- **Description**: Token-by-token streaming not supported. Full response returned at once.
- **Impact**: Poor UX for long responses; no progressive rendering.
- **Workaround**: None. Wait for Sprint 2 implementation.
- **Target Fix**: Sprint 2 (LangGraph + streaming)

### ISSUE-002: Real LLM Provider Configuration (partially resolved)
- **Severity**: Low
- **Component**: ModelProvider
- **Description**: `nvidia_build` (NVIDIA Build API) and `google` (Gemini
  OpenAI-compatibility endpoint) are implemented. NVIDIA is **VERIFIED LIVE**
  (real request, 2026-10-28). Gemini live verification is **BLOCKED** — no
  `GEMINI_API_KEY` is configured. OpenAI/Anthropic direct adapters are not
  implemented.
- **Impact**: CI cannot exercise a real provider without network and keys;
  Gemini quality is unverified.
- **Workaround**: Offline fakes for tests; `mock` for local development;
  `nvidia_build` for real smoke tests.
- **Target Fix**: Supply `GEMINI_API_KEY` and run the Gemini smoke test.

### ISSUE-003: Frontend is Legacy Static Files
- **Severity**: Low
- **Component**: Frontend (`/frontend`)
- **Description**: HTML/JS/CSS served statically. No React/Vue build, no HMR, no TypeScript.
- **Impact**: Hard to maintain; no modern DX.
- **Workaround**: API works with any client; use Postman/curl for testing.
- **Target Fix**: Sprint 2 (rewrite with React/Next.js)

### ISSUE-004: TestClient Monkeypatch in test_chat.py
- **Severity**: Low
- **Component**: Tests
- **Description**: TestClient has compatibility issue with FastAPI lifespan; workaround in test file.
- **Impact**: Test runs but with warning.
- **Workaround**: Monkeypatch applied in test file.
- **Target Fix**: Investigate FastAPI TestClient + lifespan events

### ISSUE-005: No Rate Limiting Enforced
- **Severity**: Medium
- **Component**: Middleware
- **Description**: Rate limiting designed but not implemented in middleware.
- **Impact**: API vulnerable to abuse.
- **Workaround**: None. Add Redis-based middleware.
- **Target Fix**: Sprint 2

### ISSUE-006: Pydantic v2 Deprecation Warnings
- **Severity**: Low
- **Component**: Skills Registry
- **Description**: `output.dict()` deprecated in Pydantic v2; should use `output.model_dump()`.
- **Impact**: Deprecation warnings in test output.
- **Workaround**: None. Update to `model_dump()`.
- **Target Fix**: Next code touch

### ISSUE-007: PyPDF2 Deprecation Warning
- **Severity**: Low
- **Component**: DocumentService
- **Description**: PyPDF2 deprecated; should migrate to `pypdf`.
- **Impact**: Warning on import.
- **Workaround**: None. Drop-in replacement available.
- **Target Fix**: Next code touch

### ISSUE-008: SQLAlchemy Declarative Base Warning
- **Severity**: Low
- **Component**: Database
- **Description**: `declarative_base()` deprecated in SQLAlchemy 2.0; use `orm.declarative_base()`.
- **Impact**: Warning on startup.
- **Workaround**: None. Update import.
- **Target Fix**: Next code touch

---

## Resolved Issues (Sprint 1)

### FIXED-001: Missing psycopg/pgvector Dependencies
- **Fixed**: 2026-10-20
- **Resolution**: Added `psycopg[binary]==3.3.6` and `pgvector==0.5.1` to requirements.txt

### FIXED-002: Missing tenant_id in Test Data
- **Fixed**: 2026-10-20
- **Resolution**: Updated all tests to include `tenant_id` when creating users, conversations, messages, documents

### FIXED-003: chunk_metadata JSON Serialization
- **Fixed**: 2026-10-20
- **Resolution**: Changed `chunk_metadata={}` to `chunk_metadata=json.dumps({})` in rag_service.py

### FIXED-004: delete_document FK Violations
- **Fixed**: 2026-10-20
- **Resolution**: Added cascade delete for DocumentChunk before Document deletion

### FIXED-005: Message Creation Missing tenant_id
- **Fixed**: 2026-10-20
- **Resolution**: Added `tenant_id` to user message creation in chat_service.py

### FIXED-006: list_documents Missing tenant_id Parameter
- **Fixed**: 2026-10-20
- **Resolution**: Updated test calls to include tenant_id

---

## Technical Debt

| Item | Effort | Priority | Description |
|------|--------|----------|-------------|
| Migrate to pypdf | Low | Low | Replace PyPDF2 with pypdf |
| Update Pydantic v2 calls | Low | Low | Replace `.dict()` with `.model_dump()` |
| SQLAlchemy 2.0 imports | Low | Low | Use `orm.declarative_base()` |
| Add integration tests for auth | Medium | Medium | Test login, register, token refresh |
| Add E2E tests with real LLM | High | Medium | Requires API keys |
| Implement rate limiting | Medium | High | Redis sliding window |
| Add structured logging | Medium | Medium | JSON logs with trace_id |
| Add metrics endpoint | Medium | Low | Prometheus /health/metrics |

---

## Limitations by Design

| Limitation | Reason | Mitigation |
|------------|--------|------------|
| No token refresh | Simplicity | Short expiry (30 min); re-login |
| No document versioning | Scope | Immutable uploads; re-upload for changes |
| Single embedding model | Scope | Configurable via env var |
| No multi-language support | Scope | Embedding model is English-only |
| No async file processing | Scope | Sync upload; background tasks later |

---

*Last updated: 2026-10-20 — Sprint 1 complete, Sprint 2 planning*
