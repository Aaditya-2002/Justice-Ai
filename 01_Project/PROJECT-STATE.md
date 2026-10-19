# PROJECT-STATE.md — Current Implementation Snapshot

> **Single source of truth for project status.** Update after every meaningful change.

---

## Sprint Status

| Sprint | Status | Completion | Notes |
|--------|--------|------------|-------|
| Sprint 1: Foundation & Auth | ✅ **Complete** | 100% | All infrastructure, auth, tenant isolation, RAG basics |
| Sprint 2: LangGraph Orchestration | 📋 **Planned** | 0% | Awaiting Sprint 1 verification |

---

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
=========================== 19 passed in 123.60s ================
tests/test_chat.py::test_root                    PASSED
tests/test_chat.py::test_health_live             PASSED
tests/test_chat.py::test_health_ready            PASSED
tests/test_chat.py::test_chat_endpoint           PASSED
tests/test_chat.py::test_skill_invocation        PASSED
tests/test_rag_service.py::test_rag_service      PASSED
tests/test_rag_verification.py::test_rag_cross_user_access  PASSED
tests/test_rag_verification.py::test_rag_invalid_document_id  PASSED
tests/test_rag_verification.py::test_rag_no_documents        PASSED
tests/test_rag_verification.py::test_rag_chunk_metadata      PASSED
tests/test_rag_verification.py::test_rag_citation_integrity  PASSED
tests/test_skill_authorization.py::test_skill_authorization_required_permissions  PASSED
tests/test_skill_authorization.py::test_skill_authorization_missing_permissions  PASSED
tests/test_skill_authorization.py::test_skill_authorization_unknown_identity  PASSED
tests/test_skills.py::test_word_count_skill_registered  PASSED
tests/test_skills.py::test_word_count_skill_execution  PASSED
tests/test_skills.py::test_word_count_skill_invalid_input  PASSED
tests/test_skills.py::test_skill_not_found  PASSED
tests/test_skills.py::test_skill_registry_execute_skill  PASSED
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
| No GitHub Actions secrets configured | Medium | 🔧 Pending | Need to add DB/Redis service containers |

---

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
Last commit: eca1e53 "feat: Complete Sprint 1 Foundation & Infrastructure..."
Working tree: CLEAN (no uncommitted changes)
```

---

## Next Actions (Priority Order)

1. **Configure GitHub Actions secrets** for CI/CD (PostgreSQL, Redis service containers)
2. **Verify CI pipeline runs** on push/PR
3. **Begin Sprint 2**: Read `02_Architecture/ARCHITECTURE.md` and ADRs for LangGraph design
4. **Implement PostgresSaver** with tenant-scoped checkpoint namespace
5. **Add streaming support** to ChatService and frontend

---

*Updated: 2026-10-20 02:30 IST — All Sprint 1 acceptance criteria met*
