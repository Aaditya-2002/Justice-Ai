# PROJECT.md — Justice AI Overview

## Project Summary

**Justice AI** is a multi-tenant, RAG-enabled legal assistant platform with:
- **Authentication**: JWT-based with tenant isolation
- **Document Processing**: PDF, DOCX, TXT upload with text extraction
- **RAG Pipeline**: Chunking, pgvector embeddings (384-dim), cosine similarity search
- **Skill System**: Extensible `/skill` invocation with RBAC authorization
- **Multi-tenancy**: ContextVar-scoped `tenant_id` on all queries

## Goals

1. **Legal Q&A**: Answer legal questions using uploaded documents as context
2. **Citation Integrity**: Every response cites source chunks with similarity scores
3. **Tenant Isolation**: Zero data leakage between tenants (law firms, orgs)
4. **Extensibility**: Skill framework for domain-specific tools (summarize, analyze, etc.)

## Scope (Sprint 1 — Complete)

| Component | Status | Notes |
|-----------|--------|-------|
| PostgreSQL + pgvector | ✅ | Version 18.6, Vector(384) embeddings |
| Alembic migrations | ✅ | Multi-tenant schema with `tenant_id` FKs |
| Redis | ✅ | Session cache, rate limiting ready |
| JWT Auth + RBAC | ✅ | `tenant_id` in claims, ContextVar isolation |
| Document upload/processing | ✅ | PDF, DOCX, TXT → chunks → embeddings |
| RAG retrieval + citations | ✅ | Cosine similarity, citation metadata |
| Skill system + auth | ✅ | `/skill` command, permission enforcement |
| Test suite (19 tests) | ✅ | All passing |

## Scope (Sprint 2 — Planned)

| Component | Status | Notes |
|-----------|--------|-------|
| LangGraph orchestration | 📋 | Graph nodes, state, checkpointing |
| PostgresSaver integration | 📋 | Tenant-scoped checkpoints |
| Advanced RAG (hybrid search) | 📋 | BM25 + vector, reranking |
| Streaming responses | 📋 | Token-by-token UI |
| Frontend integration | 📋 | Chat UI with citations |

## Non-Goals

- Fine-tuning LLMs (uses mock/sentence-transformers providers)
- Real-time collaboration (single-user conversations)
- Document versioning (immutable uploads)

## Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| API Framework | FastAPI | 0.133.1 |
| ORM | SQLAlchemy | 2.1.4 |
| Database | PostgreSQL | 18.6 |
| Vector Extension | pgvector | 0.5.1 |
| Cache | Redis | 7.x |
| Embeddings | sentence-transformers | 6.1.0 (all-MiniLM-L6-v2) |
| Auth | PyJWT + passlib | 2.13.0 / 1.7.4 |
| Migrations | Alembic | 1.13.1 |
| Testing | pytest + pytest-asyncio | 9.1.1 / 1.4.0 |

## Repository Structure

```
Justice AI/
├── AGENTS.md                 # Agent entry point (this system)
├── requirements.txt          # Pinned dependencies
├── Dockerfile                # Container build
├── .github/workflows/ci.yml  # CI/CD pipeline
├── alembic/                  # Database migrations
├── app/
│   ├── core/                 # Config, database, security, embeddings
│   ├── models/               # SQLAlchemy models (all tenant-scoped)
│   ├── routers/              # FastAPI route handlers
│   ├── services/             # Business logic (Chat, Document, RAG, Auth)
│   ├── skills/               # Skill registry + implementations
│   └── main.py               # App entry point
├── tests/                    # 19 passing tests
├── frontend/                 # Static HTML/JS/CSS (legacy)
├── uploads/                  # Uploaded document storage
└── 01_Project/...07_Knowledge/  # This documentation system
```

## External References

- **Obsidian Knowledge Base**: `C:\Obsidian\Hermes\Justice-AI-Research\`
- **GitHub Repository**: https://github.com/Aaditya-2002/Justice-Ai
- **Architecture ADRs**: See `02_Architecture/ARCHITECTURE.md` and Obsidian `14-Architecture-Synthesis/`

---

*Last updated: 2026-10-20 — Sprint 1 complete, all tests passing*
