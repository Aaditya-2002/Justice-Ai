# TESTING.md — Testing Strategy & Requirements

## Test Pyramid

```
        E2E (2)
       /        Integration (5)
     /          Unit (12)    Contract (0)
```

**Current**: 19 tests (12 unit, 5 integration, 2 E2E-ish)

---

## Operating Mode Tests (Sprint 2)

### Normal Mode (Mode A) Tests
- [ ] `test_normal_mode_with_mock_llm` — Verify full graph execution with mock model provider
- [ ] `test_normal_mode_checkpointing` — Verify PostgresSaver checkpoint save/retrieve works synchronously
- [ ] `test_normal_mode_tenant_isolation` — Verify tenant_id scoping in all queries
- [ ] `test_normal_mode_citation_validation` — Verify citations match retrieved sources
- [ ] `test_normal_mode_skill_authorization` — Verify skill permission enforcement
- [ ] `test_normal_mode_rang_retrieval` — Verify RAG pipeline with pgvector search
- [ ] `test_normal_mode_error_handling` — Verify LangGraph exceptions trigger fallback

### Fallback Mode (Mode B) Tests
- [ ] `test_fallback_mode_without_llm` — Verify response generation when LLM unavailable
- [ ] `test_fallback_evidence_based_response` — Verify evidence-based response without LLM
- [ ] `test_fallback_no_fabrication` — Verify no fabricated citations or sources
- [ ] `test_fallback_insufficient_evidence` — Verify "insufficient evidence" response
- [ ] `test_fallback_tenant_isolation` — Verify tenant isolation still applies in fallback
- [ ] `test_fallback_authentication` — Verify authentication persists in fallback mode

### API Failure and Provider Fallback Tests
- [ ] `test_provider_timeout_handling` — Verify graceful handling of LLM API timeouts
- [ ] `test_provider_rate_limit_handling` — Verify rate limit retries are bounded
- [ ] `test_fallback_activation_threshold` — Verify fallback activates after max retries
- [ ] `test_recovery_from_fallback` — Verify system returns to normal mode after provider recovers

### Graph Execution Tests
- [ ] `test_graph_synchronous_execution` — Verify graph runs without ainvoke/async issues
- [ ] `test_graph_checkpoint_save` — Verify checkpoint is saved via PostgresSaver
- [ ] `test_graph_checkpoint_restore` — Verify checkpoint can be restored
- [ ] `test_graph_node_transitions` — Verify all 8 node transitions work correctly

---


## Test Categories

### Unit Tests (12)
| Test File | Focus | Count |
|-----------|-------|-------|
| `test_skills.py` | Skill registry, wordcount | 5 |
| `test_skill_authorization.py` | Permission enforcement | 3 |
| `test_chat.py` (partial) | Health, root | 4 |

### Integration Tests (5)
| Test File | Focus | Count |
|-----------|-------|-------|
| `test_rag_service.py` | RAG pipeline | 1 |
| `test_rag_verification.py` | RAG behavior | 5 |

### E2E-ish Tests (2)
| Test File | Focus | Count |
|-----------|-------|-------|
| `test_chat.py::test_chat_endpoint` | API flow | 1 |
| `test_chat.py::test_skill_invocation` | Full chat+skill | 1 |

---

## Test Requirements

### Mandatory for All Changes
- [ ] **All 19 existing tests pass**
- [ ] **New tests for new behavior**
- [ ] **No flaky tests** (fix immediately)
- [ ] **Coverage maintained** (target: 80%+)

### Test Isolation
- Each test creates/cleans its own data
- Use unique IDs (UUID) to avoid collisions
- Clean up in `finally` blocks
- No shared state between tests

### Database Testing
```python
# Use real PostgreSQL (not SQLite)
# Connection via DATABASE_URL env var
# Clean up: DELETE in reverse FK order
# Order: chunks → documents → messages → conversations → users
```

---

## Running Tests

### Local
```bash
# All tests
python -m pytest tests/ -v --tb=short

# Specific module
python -m pytest tests/test_rag_service.py -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=term-missing

# Stop on first failure
python -m pytest tests/ -x
```

### CI Pipeline
```yaml
# .github/workflows/ci.yml
services:
  postgres:
    image: pgvector/pgvector:pg18
    env:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: justice_ai
  redis:
    image: redis:7-alpine
```

---

## Test Patterns

### Fixtures (Recommended)
```python
# tests/conftest.py
import pytest
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.base import Base

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine.connect())
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
```

### Async Tests
```python
# Use pytest-asyncio
@pytest.mark.asyncio
async def test_rag_retrieval():
    db = next(get_db())
    service = RAGService(db)
    chunks = await service.retrieve_relevant_chunks(...)
    assert len(chunks) > 0
```

### Test Data Cleanup
```python
try:
    # Setup
    user = User(id="test-user", tenant_id=TENANT_ID, ...)
    db.add(user)
    db.commit()
    
    # Test
    result = await service.do_something(user.id)
    assert result.success
    
finally:
    # Cleanup in reverse FK order
    db.query(DocumentChunk).filter(...).delete()
    db.query(Document).filter(...).delete()
    db.query(User).filter(User.id == "test-user").delete()
    db.commit()
```

---

## Coverage Targets

| Module | Target | Current |
|--------|--------|---------|
| `app/services/` | 80% | ~70% |
| `app/routers/` | 70% | ~60% |
| `app/models/` | 90% | ~85% |
| `app/core/` | 80% | ~75% |
| **Overall** | **80%** | **~72%** |

### Exclusions
```bash
# .coveragerc
[run]
omit =
    */tests/*
    */migrations/*
    */alembic/*
    */venv/*
    */__pycache__/*
```

---

## Test Data Management

### Test Tenant
```python
TENANT_ID = "712dd85e-398d-4890-a030-07f811bc159f"  # default tenant
```

### Unique IDs
```python
import uuid
user_id = f"test-user-{uuid.uuid4().hex[:8]}"
doc_id = f"test-doc-{uuid.uuid4().hex[:8]}"
```

### Helper Functions
```python
def create_test_user(db, user_id, tenant_id=TENANT_ID):
    user = User(id=user_id, tenant_id=tenant_id, ...)
    db.add(user)
    db.commit()
    return user

def cleanup_test_data(db, user_id):
    db.query(DocumentChunk).filter(DocumentChunk.document_id.like(f"%{user_id}%")).delete()
    db.query(Document).filter(Document.user_id == user_id).delete()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
```

---

## Operating Mode Tests (Sprint 2)

### Normal Mode (Mode A) Tests
- [ ] `test_normal_mode_with_mock_llm` — Verify full graph execution with mock model provider
- [ ] `test_normal_mode_checkpointing` — Verify PostgresSaver checkpoint save/retrieve works synchronously
- [ ] `test_normal_mode_tenant_isolation` — Verify tenant_id scoping in all queries
- [ ] `test_normal_mode_citation_validation` — Verify citations match retrieved sources
- [ ] `test_normal_mode_skill_authorization` — Verify skill permission enforcement
- [ ] `test_normal_mode_rang_retrieval` — Verify RAG pipeline with pgvector search
- [ ] `test_normal_mode_error_handling` — Verify LangGraph exceptions trigger fallback

### Fallback Mode (Mode B) Tests
- [ ] `test_fallback_mode_without_llm` — Verify response generation when LLM unavailable
- [ ] `test_fallback_evidence_based_response` — Verify evidence-based response without LLM
- [ ] `test_fallback_no_fabrication` — Verify no fabricated citations or sources
- [ ] `test_fallback_insufficient_evidence` — Verify "insufficient evidence" response
- [ ] `test_fallback_tenant_isolation` — Verify tenant isolation still applies in fallback
- [ ] `test_fallback_authentication` — Verify authentication persists in fallback mode

### API Failure and Provider Fallback Tests
- [ ] `test_provider_timeout_handling` — Verify graceful handling of LLM API timeouts
- [ ] `test_provider_rate_limit_handling` — Verify rate limit retries are bounded
- [ ] `test_fallback_activation_threshold` — Verify fallback activates after max retries
- [ ] `test_recovery_from_fallback` — Verify system returns to normal mode after provider recovers

### Graph Execution Tests
- [ ] `test_graph_synchronous_execution` — Verify graph runs without ainvoke/async issues
- [ ] `test_graph_checkpoint_save` — Verify checkpoint is saved via PostgresSaver
- [ ] `test_graph_checkpoint_restore` — Verify checkpoint can be restored
- [ ] `test_graph_node_transitions` — Verify all 8 node transitions work correctly

---

## Mocking Guidelines

### DO Mock
- External LLM providers (OpenAI, Anthropic)
- External APIs (email, webhooks)
- Time-dependent functions (`datetime.now()`)
- File system (use `tempfile`)

### DON'T Mock
- Database (use real PostgreSQL)
- Redis (use real Redis)
- Internal services (ChatService, DocumentService)
- Authentication middleware

---

## Continuous Integration

### Pipeline Stages
1. **Lint** → `black --check . && isort --check-only . && flake8 .`
2. **Type Check** → `mypy app/` (optional)
3. **Test** → `pytest tests/ -v --tb=short`
4. **Build** → `docker build -t justice-ai:${SHA} .`
5. **Smoke Test** → `docker run ... && curl /health/live`

### Required Checks
- [ ] All tests pass
- [ ] Coverage >= 80% (overall)
- [ ] No new linting errors
- [ ] Docker build succeeds
- [ ] Health checks pass

---

## Debugging Failed Tests

### Common Issues
| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: psycopg` | Missing dependency | `pip install psycopg[binary]` |
| `NotNullViolation: tenant_id` | Missing tenant_id in create | Add `tenant_id=TENANT_ID` |
| `ForeignKeyViolation: user_id` | User not created | Create user first |
| `cannot adapt type 'dict'` | JSON not serialized | Use `json.dumps()` |
| `UniqueViolation: id` | Test data not cleaned | Clean up in `finally` |

### Verbose Output
```bash
# Full traceback
pytest tests/ -v --tb=long

# Show stdout/stderr
pytest tests/ -v -s

# Single test with debug
pytest tests/test_rag_service.py::test_rag_service -v -s --tb=long
```

---

## Test Documentation

### Adding New Tests
1. Create test in appropriate `test_*.py`
2. Follow naming: `test_<feature>_<scenario>`
3. Include setup, execution, assertion, cleanup
4. Add to CI if new test file
5. Update this doc if new patterns

### Test Naming
```
test_<module>_<function>_<scenario>
test_rag_service_upload_document_success
test_rag_verification_cross_user_access_denied
test_skill_authorization_missing_admin_permission
```

---

*Test suite status: 19/19 passing as of 2026-10-20*
