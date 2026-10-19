# WORKFLOW.md — Development Workflow

## Git Workflow

### Branch Strategy
```
main (protected)
  ├── feature/*     # New features
  ├── fix/*         # Bug fixes
  ├── chore/*       # Maintenance
  └── docs/*        # Documentation
```

### Commit Convention (Conventional Commits)
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`

**Examples**:
```
feat(auth): add tenant_id to JWT claims
fix(rag): resolve chunk_metadata serialization
docs(architecture): add Sprint 2 LangGraph design
```

### Pull Request Process
1. Create feature branch from `main`
2. Implement changes with tests
3. Run full test suite locally: `pytest tests/ -v`
4. Run linting: `black --check . && isort --check-only . && flake8 .`
5. Open PR with description linking to issue/ADR
6. CI must pass (tests, lint, build)
7. Code review required
8. Squash merge to `main`

---

## Local Development Setup

### Prerequisites
- Python 3.12+
- PostgreSQL 18+ with pgvector
- Redis 7+
- Git

### Quick Start
```bash
# 1. Clone and setup
git clone https://github.com/Aaditya-2002/Justice-Ai.git
cd Justice-Ai

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, SECRET_KEY, etc.

# 5. Start infrastructure
redis-server  # or redis-server.exe on Windows
# PostgreSQL should be running with pgvector extension

# 6. Run migrations
alembic upgrade head

# 7. Run tests (verify baseline)
pytest tests/ -v --tb=short

# 8. Start development server
uvicorn app.main:app --reload
```

---

## Database Workflow

### Creating Migrations
```bash
# After model changes
alembic revision --autogenerate -m "description of change"

# Review generated migration in alembic/versions/
# Apply
alembic upgrade head
```

### Migration Safety Rules
- **Never edit applied migrations** — create new ones
- **Test migrations locally** before committing
- **Backup production DB** before migrating
- **Idempotent operations** where possible

---

## Testing Workflow

### Test Organization
```
tests/
├── test_chat.py              # API endpoints, chat flow
├── test_rag_service.py       # RAG pipeline integration
├── test_rag_verification.py  # RAG behavior verification
├── test_skills.py            # Skill registry, wordcount
├── test_skill_authorization.py # Permission enforcement
└── conftest.py               # (if needed) fixtures
```

### Running Tests
```bash
# All tests
pytest tests/ -v --tb=short

# Specific module
pytest tests/test_rag_service.py -v

# With coverage
pytest tests/ --cov=app --cov-report=term-missing

# Parallel (if available)
pytest tests/ -n auto
```

### Test Principles
- **Isolation**: Each test cleans up its data
- **Deterministic**: No flaky tests; fix immediately
- **Real dependencies**: Use real PostgreSQL/Redis in CI
- **Mock external**: Mock LLM providers, not database

---

## Code Quality Standards

### Formatting (enforced by CI)
```bash
black .              # Format
isort .              # Sort imports
flake8 .             # Lint
mypy app/            # Type check (optional)
```

### Type Hints
- **Required** for all public functions
- **Use `typing`** imports: `List`, `Dict`, `Optional`, `Any`
- **Pydantic models** for request/response schemas

### Naming Conventions
| Element | Convention |
|---------|------------|
| Files | `snake_case.py` |
| Classes | `PascalCase` |
| Functions | `snake_case` |
| Constants | `UPPER_SNAKE_CASE` |
| Private | `_leading_underscore` |

---

## Code Review Checklist

### Author Self-Review
- [ ] Tests added/updated for new behavior
- [ ] All existing tests pass
- [ ] No hardcoded secrets or credentials
- [ ] Database changes have migrations
- [ ] Documentation updated (AGENTS.md, PROJECT-STATE.md)
- [ ] No `print()` statements in production code

### Reviewer Focus
- [ ] Logic correctness & edge cases
- [ ] Security implications (SQLi, XSS, auth bypass)
- [ ] Tenant isolation maintained
- [ ] Performance (N+1 queries, large payloads)
- [ ] Consistency with existing patterns

---

## Release Process

### Versioning
- **Semantic Versioning**: MAJOR.MINOR.PATCH
- **main branch** = latest stable
- **Tags**: `v1.0.0`, `v1.1.0`, etc.

### Release Steps
1. Update `CHANGELOG.md`
2. Create release branch: `release/v1.x.0`
3. Final testing & bug fixes
4. Tag release: `git tag v1.x.0`
5. CI builds & publishes Docker image
6. Merge to main, delete release branch

---

## Debugging Common Issues

| Issue | Resolution |
|-------|------------|
| `ModuleNotFoundError: psycopg` | `pip install psycopg[binary]` |
| `ModuleNotFoundError: pgvector` | `pip install pgvector` |
| `NotNullViolation: tenant_id` | Ensure `tenant_id` in all model creates |
| `ForeignKeyViolation: user_id` | Create user before document/conversation |
| `cannot adapt type 'dict'` | Use `json.dumps()` for JSON text columns |
| TestClient 401 on protected routes | Check JWT middleware, token format |
| Alembic `CommandError` | Check `alembic.ini` `sqlalchemy.url` |

---

## IDE Configuration

### VS Code (`.vscode/settings.json`)
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": "explicit"
  },
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"]
}
```

---

*Follow this workflow for all changes. Update PROJECT-STATE.md after completing tasks.*
