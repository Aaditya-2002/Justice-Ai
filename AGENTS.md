# AGENTS.md - Justice AI Coding Agent Instructions

> **Entry point for all AI coding agents working on this repository.**
> Read this file completely before starting any work.

---

## 1. Required Reading Order

Before making any changes, read these files in order:

1. **This file** (`AGENTS.md`) — Agent instructions and workflow
2. **`01_Project/PROJECT.md`** — Project overview, goals, and scope
3. **`01_Project/PROJECT-STATE.md`** — Current implementation status, dependencies, and blockers
4. **Relevant architecture docs** in `02_Architecture/` for the task
5. **Relevant development docs** in `03_Development/` for coding standards
6. **Relevant database/API docs** in `04_Database-API/` for data models and contracts
7. **Security & Testing docs** in `05_Security-Testing/` for requirements

---

## 2. Core Principles

| Principle | Description |
|-----------|-------------|
| **Inspect First** | Always read actual code before trusting documentation. Verify implementation matches docs. |
| **Reuse Over Rebuild** | Use existing services, models, and utilities. Do not duplicate functionality. |
| **Research Official Docs** | When unsure about library behavior, consult official documentation (FastAPI, SQLAlchemy, pgvector, etc.). |
| **Test Every Change** | Run relevant tests before and after changes. All tests must pass. |
| **Protect Secrets & Data** | Never commit credentials, tokens, or real user data. Use environment variables. |
| **Preserve Databases** | Do not drop/recreate databases. Use migrations. Backup before destructive operations. |
| **Update State** | After meaningful changes, update `PROJECT-STATE.md` and relevant docs. |

---

## 3. Project-Specific Rules

### Database (PostgreSQL + pgvector)
- **Multi-tenant by design**: Every table has `tenant_id` (FK to `tenants.id`)
- **Vector embeddings**: Stored in `document_chunks.embedding` as `Vector(384)` (pgvector)
- **Migrations**: Managed by Alembic. Never edit migration files after they're applied.
- **Connection**: `DATABASE_URL` env var (default: `postgresql://postgres@127.0.0.1:5432/justice_ai`)

### Authentication & Authorization
- **JWT tokens** with `tenant_id` in claims
- **ContextVar isolation**: `tenant_id` extracted from JWT and stored in `ContextVar` for request-scoped tenant isolation
- **RBAC permissions**: Comma-separated strings in `users.permissions` (e.g., `admin,lawyer`)
- **Skill authorization**: Skills declare `required_permissions`; registry enforces at execution time

### Key Services (Reuse These)
| Service | Location | Responsibility |
|---------|----------|----------------|
| `ChatService` | `app/services/chat_service.py` | Conversation flow, skill invocation, RAG integration |
| `DocumentService` | `app/services/document_service.py` | Upload, list, delete, text extraction |
| `RAGService` | `app/services/rag_service.py` | Chunking, embeddings, similarity search |
| `ConversationService` | `app/services/conversation_service.py` | CRUD for conversations |
| `AuthService` | `app/services/auth_service.py` | User registration, login, tenant management |
| `EmbeddingProvider` | `app/core/embedding_provider.py` | Abstract interface; mock or sentence-transformers |

### Models (All Scoped by `tenant_id`)
- `User` — `app/models/user.py`
- `Tenant` — `app/models/tenant.py`
- `Conversation` — `app/models/conversation.py`
- `Message` — `app/models/message.py`
- `Document` — `app/models/document.py`
- `DocumentChunk` — `app/models/document_chunk.py` (has `embedding: Vector(384)`)

---

## 4. Development Workflow

### Before Starting
```bash
# 1. Activate venv and check dependencies
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2. Verify infrastructure
redis-cli ping          # Should return PONG
psql -h 127.0.0.1 -U postgres -d justice_ai -c "SELECT 1"  # Should return 1

# 3. Run tests to establish baseline
python -m pytest tests/ -v --tb=short
```

### During Development
- Make small, focused changes
- Run tests frequently: `python -m pytest tests/test_<module>.py -v`
- Check for new warnings or deprecations
- Do not modify `.env` or commit it

### Before Committing
```bash
# 1. Run full test suite
python -m pytest tests/ -v --tb=short

# 2. Run linting (if configured)
black --check .
isort --check-only .
flake8 .

# 3. Update PROJECT-STATE.md with:
#    - Changed files
#    - Test results
#    - New dependencies
#    - Blockers or decisions
```

---

## 5. Testing Requirements

| Test Type | Location | When to Run |
|-----------|----------|-------------|
| Unit (auth, skills, models) | `tests/test_*.py` | Every change |
| Integration (RAG, chat, documents) | `tests/test_rag_*.py`, `tests/test_chat.py` | After service changes |
| Authorization | `tests/test_skill_authorization.py` | After permission changes |

**All 19 tests must pass** before considering a task complete.

---

## 6. Common Commands

| Task | Command |
|------|---------|
| Run all tests | `python -m pytest tests/ -v --tb=short` |
| Run specific test | `python -m pytest tests/test_rag_service.py -v` |
| Run with coverage | `python -m pytest tests/ --cov=app --cov-report=term-missing` |
| Create migration | `alembic revision --autogenerate -m "description"` |
| Apply migrations | `alembic upgrade head` |
| Start app | `uvicorn app.main:app --reload` |
| Start Redis | `redis-server` (or `redis-server.exe` on Windows) |

---

## 7. Agent-Specific Configuration

### GitHub Copilot
Create `.github/copilot-instructions.md` with:
```markdown
# Copilot Instructions for Justice AI
- Follow AGENTS.md workflow
- Use existing services (ChatService, DocumentService, RAGService)
- All models scoped by tenant_id
- JWT auth with tenant_id in claims
- pgvector for embeddings (Vector(384))
```

### Cursor / Windsurf
Add `.cursorrules` or `.windsurfrules` pointing to `AGENTS.md`

### Generic Agents
Any agent should be instructed to:
1. Read `AGENTS.md` first
2. Follow the Required Reading Order
3. Update `PROJECT-STATE.md` after changes

---

## 8. Safety Checklist

Before any destructive action, verify:
- [ ] Database backup exists or changes are migration-based
- [ ] No credentials in code or commit history
- [ ] Tests pass before and after
- [ ] `PROJECT-STATE.md` updated
- [ ] Git status clean (no unintended changes)

---

## 9. Escalation

If you encounter:
- **Schema conflicts** → Check Alembic history, do not force
- **Test failures unrelated to your change** → Clean DB, re-run baseline
- **Missing dependencies** → Add to `requirements.txt` with version pin
- **Architecture uncertainty** → Read `02_Architecture/ARCHITECTURE.md` and ADRs in Obsidian

---

*Last updated: 2026-10-20 — All 19 tests passing, Sprint 1 complete*
