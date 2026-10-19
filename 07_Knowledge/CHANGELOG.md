# CHANGELOG.md — Justice AI Changelog

## Format

Based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/):
- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for removed features
- **Fixed** for bug fixes
- **Security** for vulnerability fixes

---

## [Unreleased] — Sprint 2 (Planned)

### Added
- LangGraph orchestration core with state management
- PostgresSaver integration with tenant-scoped checkpoints
- Streaming response support (token-by-token)
- OpenAI/Anthropic model provider implementations
- React/Next.js frontend rewrite
- Rate limiting middleware (Redis sliding window)
- WebSocket support for streaming chat
- Prometheus metrics endpoint

### Changed
- ChatService refactored for LangGraph integration
- RAG retrieval enhanced with hybrid search (BM25 + vector)
- Skill system async support

### Fixed
- Streaming response handling
- Real LLM provider integration

---

## [1.0.0] — 2026-10-20 (Sprint 1 Complete)

### Added
- **Multi-tenant PostgreSQL schema** with `tenant_id` on all tables
- **pgvector integration** for embedding storage (`VECTOR(384)`)
- **JWT authentication** with `tenant_id` in claims
- **ContextVar-based tenant isolation** middleware
- **Role-based access control** (permissions CSV in users table)
- **Skill system** with decorator registry and RBAC enforcement
- **Document processing pipeline**: upload → extract → chunk → embed → store
- **RAG pipeline**: query embedding → cosine similarity → top-k retrieval → citations
- **Alembic migrations** for schema evolution
- **Redis integration** for sessions and rate limiting (planned)
- **Comprehensive test suite** (19 tests passing)
- **Docker & Docker Compose** for local development
- **Kubernetes manifests** for production deployment
- **Documentation system** (AGENTS.md + 01_Project/ through 07_Knowledge/)

### Changed
- All models now include `tenant_id` NOT NULL FK
- ChatService updated for tenant-scoped operations
- DocumentService cascades chunk deletion
- Message creation includes tenant_id

### Fixed
- `psycopg` and `pgvector` dependencies added
- Test data includes `tenant_id` for all entities
- `chunk_metadata` JSON serialization fixed
- `delete_document` cascades to chunks
- Message creation includes `tenant_id`
- API calls include `tenant_id` parameter

### Security
- bcrypt password hashing (cost=12)
- JWT HS256 with 30-min expiry
- `tenant_id` in JWT claims
- ContextVar request-scoped isolation
- Parameterized SQL queries (no injection)
- File upload validation (type, size, path)

---

## [0.1.0] — 2026-10-18 (Initial Implementation)

### Added
- Basic FastAPI application structure
- User registration and login
- Conversation and message CRUD
- Document upload with text extraction (PDF, DOCX, TXT)
- Simple RAG with mock embeddings
- Skill registry with wordcount skill
- SQLite database (initial prototype)

### Known Issues (Resolved in 1.0.0)
- No multi-tenancy
- No vector search (mock embeddings only)
- No authentication middleware
- No test suite
- No deployment configuration

---

## Migration Notes

### 0.1.0 → 1.0.0 (Breaking Changes)

| Change | Action Required |
|--------|-----------------|
| Database: PostgreSQL + pgvector required | Provision PostgreSQL 18+, enable pgvector |
| Schema: `tenant_id` on all tables | Run `alembic upgrade head` |
| Auth: JWT with `tenant_id` claim | Update token generation/validation |
| Config: New env vars required | Set `DATABASE_URL`, `SECRET_KEY`, etc. |
| Dependencies: `psycopg`, `pgvector` added | `pip install -r requirements.txt` |

---

## Versioning Policy

- **MAJOR**: Breaking API changes, schema changes requiring migration
- **MINOR**: New features, backward-compatible
- **PATCH**: Bug fixes, documentation, dependencies

### Release Tags
```
v1.0.0 — Sprint 1 complete
v1.1.0 — Sprint 2 (LangGraph) complete
v1.2.0 — Streaming + real LLM
v2.0.0 — Major architecture change
```

---

## Contributors

- Hermes Agent (implementation)
- Aaditya Raj (direction, review)

---

*Changelog maintained per release. Update with each version.*
