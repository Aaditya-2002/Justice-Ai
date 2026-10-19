# DECISIONS.md — Architectural Decision Records

## ADR Format

| Field | Description |
|-------|-------------|
| **ID** | ADR-XXX (sequential) |
| **Title** | One-line summary |
| **Status** | Proposed / Accepted / Superseded |
| **Date** | YYYY-MM-DD |
| **Context** | Problem, constraints, assumptions |
| **Decision** | What was chosen |
| **Consequences** | Trade-offs, risks, follow-ups |

---

## ADR-001: Multi-Tenant Architecture with ContextVar

**Status**: Accepted  
**Date**: 2026-10-18

### Context
Need to isolate data between tenants (law firms, organizations). Each tenant must have completely separate data with zero leakage.

### Decision
Use PostgreSQL `tenant_id` foreign key on ALL tables + FastAPI middleware that extracts `tenant_id` from JWT → stores in `ContextVar` → all queries implicitly filtered.

### Consequences
- **Pros**: Simple, performant, zero cross-tenant leakage verified
- **Cons**: Must remember `tenant_id` in every model/query; ContextVar is request-scoped only
- **Follow-up**: Document pattern in CODING-STANDARDS.md

---

## ADR-002: pgvector for Embedding Storage

**Status**: Accepted  
**Date**: 2026-10-18

### Context
Need vector similarity search for RAG. Options: pgvector, Pinecone, Weaviate, Qdrant, custom FAISS.

### Decision
Use pgvector extension on PostgreSQL. Stores embeddings as `VECTOR(384)` columns, uses `<->` operator for cosine distance.

### Consequences
- **Pros**: Single database, ACID, no external dependency, SQL integration
- **Cons**: Less scalable than dedicated vector DBs; HNSW index needed at scale
- **Follow-up**: Add HNSW index when >100K chunks

---

## ADR-003: JWT with Tenant ID in Claims

**Status**: Accepted  
**Date**: 2026-10-18

### Context
Need stateless auth with tenant context. Options: session cookies, JWT, opaque tokens.

### Decision
JWT with `tenant_id` claim. Middleware decodes → validates → sets `ContextVar`. All downstream services read from ContextVar.

### Consequences
- **Pros**: Stateless, scalable, tenant_id always available
- **Cons**: Token size larger; no revocation (short expiry mitigates)
- **Follow-up**: Add token blacklist if logout needed

---

## ADR-004: Skill System with RBAC

**Status**: Accepted  
**Date**: 2026-10-19

### Context
Need extensible `/skill` command system. Skills may require permissions (e.g., admin-only).

### Decision
Decorator-based registry: `@skill_registry.register(name="x", required_permissions=["admin"])`. Execution checks user permissions against skill requirements.

### Consequences
- **Pros**: Declarative, easy to add skills, centralized auth
- **Cons**: Permissions checked at execution time (not registration)
- **Follow-up**: Add skill versioning, async skill support

---

## ADR-005: Mock + Sentence-Transformers Embedding Providers

**Status**: Accepted  
**Date**: 2026-10-19

### Context
Need embeddings for RAG. Options: OpenAI, Cohere, HuggingFace, local sentence-transformers.

### Decision
Abstract `EmbeddingProvider` interface with two implementations:
1. `MockEmbeddingProvider` — deterministic random vectors for testing
2. `SentenceTransformerEmbeddingProvider` — `all-MiniLM-L6-v2` (384-dim) for dev/prod

### Consequences
- **Pros**: Testable without API keys, local dev works offline, swappable
- **Cons**: Mock not suitable for quality eval; sentence-transformers slower than API
- **Follow-up**: Add OpenAI/Anthropic providers for production

---

## ADR-006: Alembic for Migrations

**Status**: Accepted  
**Date**: 2026-10-18

### Context
Need schema evolution with multi-tenant tables and pgvector.

### Decision
Alembic with autogenerate. Migration files committed to repo. Run `alembic upgrade head` on deploy.

### Consequences
- **Pros**: Version controlled, repeatable, supports pgvector
- **Cons**: Autogenerate sometimes misses pgvector types; manual review needed
- **Follow-up**: Add migration test in CI

---

## ADR-007: Redis for Sessions + Rate Limiting

**Status**: Accepted  
**Date**: 2026-10-19

### Context
Need session storage and rate limiting. Options: in-memory, Redis, database.

### Decision
Redis for both. Session keys: `session:{token}`. Rate limit keys: `ratelimit:{tenant}:{ip}:{endpoint}`. Sliding window algorithm.

### Consequences
- **Pros**: Fast, scalable, TTL support, shared across instances
- **Cons**: Additional infrastructure dependency
- **Follow-up**: Implement rate limiting middleware; add Redis Cluster for HA

---

## ADR-008: UUID for All Primary Keys

**Status**: Accepted  
**Date**: 2026-10-19

### Context
Need globally unique IDs across tenants. Options: auto-increment, UUID, ULID, nanoid.

### Decision
UUID v4 (via `uuid.uuid4()`) for all PKs. Document IDs, chunk IDs, conversation IDs, message IDs.

### Consequences
- **Pros**: No coordination, globally unique, no enumeration attacks
- **Cons**: Larger storage (36 chars vs 8 bytes), not sequential (index fragmentation)
- **Follow-up**: Consider UUID v7 (timestamp-ordered) for better index locality

---

## ADR-009: JSON Text Columns for Metadata

**Status**: Accepted  
**Date**: 2026-10-19

### Context
Need flexible metadata on chunks, messages, documents. Options: JSONB, TEXT+JSON, separate tables.

### Decision
Store as `TEXT` column with `json.dumps()`/`json.loads()`. Columns: `chunk_metadata`, `provider_metadata`, `token_usage`, `settings`.

### Consequences
- **Pros**: Simple, flexible, no schema migration for new fields
- **Cons**: No SQL querying inside JSON; application-level validation needed
- **Follow-up**: Migrate to JSONB if querying needed

---

## ADR-010: Chunk ID Format

**Status**: Accepted  
**Date**: 2026-10-19

### Context
Need unique, traceable chunk IDs. Options: UUID, composite, custom format.

### Decision
Format: `{document_id}-chunk-{index}`. Example: `abc123-chunk-0`.

### Consequences
- **Pros**: Traceable to document, ordered, human-readable
- **Cons**: Longer than UUID; document_id must exist first
- **Follow-up**: None

---

## ADR-011: Citation Format in Chat Response

**Status**: Accepted  
**Date**: 2026-10-19

### Context
RAG responses must cite sources. Need structured citation format.

### Decision
Response includes `citations` array with objects:
```json
{
  "document_id": "uuid",
  "filename": "doc.pdf",
  "chunk_index": 0,
  "chunk_text": "excerpt...",
  "similarity": 0.85
}
```

### Consequences
- **Pros**: Frontend can render citations, verifiable, includes similarity
- **Cons**: Increases response size; chunk_text may be long
- **Follow-up**: Add citation truncation option

---

## ADR-012: Health Endpoint Separation

**Status**: Accepted  
**Date**: 2026-10-19

### Context
Kubernetes needs separate liveness and readiness probes.

### Decision
Two endpoints:
- `/health/live` — process alive (no dependencies)
- `/health/ready` — dependencies healthy (DB, Redis)

### Consequences
- **Pros**: K8s can restart dead pods, drain unready pods
- **Cons**: Slight complexity; readiness must check all deps
- **Follow-up**: Add DB/Redis connectivity checks to ready

---

*Last updated: 2026-10-20 — All Sprint 1 ADRs accepted and implemented*
