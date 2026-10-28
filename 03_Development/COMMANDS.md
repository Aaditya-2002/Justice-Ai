# COMMANDS.md — Verified Commands Reference

> All commands tested and verified in the Justice AI development environment.

---

## Environment Setup

### Virtual Environment
```bash
# Create
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (Windows CMD)
.\venv\Scripts\activate.bat

# Deactivate
deactivate
```

### Dependencies
```bash
# Install all
pip install -r requirements.txt

# Upgrade pip first
python -m pip install --upgrade pip
pip install -r requirements.txt

# Install single package
pip install psycopg[binary]==3.3.6

# Show installed
pip list | grep -E "(fastapi|sqlalchemy|pgvector|psycopg|pytest)"
```

---

## Database Commands

### PostgreSQL (Local)
```bash
# Start PostgreSQL service
# Windows: net start postgresql-x64-18
# Linux: sudo systemctl start postgresql

# Connect as superuser
psql -U postgres

# Create database
CREATE DATABASE justice_ai;

# Enable pgvector extension
\c justice_ai
CREATE EXTENSION IF NOT EXISTS vector;

# Verify
SELECT * FROM pg_extension WHERE extname='vector';

# List tables
\dt

# Describe table
\d users
\d document_chunks
```

### Alembic Migrations
```bash
# Initialize (already done)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "add tenant_id to messages"

# Apply migrations
alembic upgrade head

# Show history
alembic history

# Show current revision
alembic current

# Downgrade (if needed)
alembic downgrade -1
```

### Database Verification
```bash
# Verify connection
psql -h 127.0.0.1 -U postgres -d justice_ai -c "SELECT 1"

# Check tenant isolation
psql -h 127.0.0.1 -U postgres -d justice_ai -c "SELECT id, tenant_id FROM users;"

# Check vector column
psql -h 127.0.0.1 -U postgres -d justice_ai -c "SELECT id, embedding FROM document_chunks LIMIT 1;"
```

---

## Redis Commands

```bash
# Start Redis
# Windows: redis-server.exe
# Linux: sudo systemctl start redis

# Test connection
redis-cli ping
# Expected: PONG

# Basic operations
redis-cli set test_key "hello"
redis-cli get test_key

# Session keys pattern
redis-cli keys "session:*"

# Rate limit keys
redis-cli keys "ratelimit:*"

# Flush all (dev only)
redis-cli flushall
```

---

## Application Commands

### Run Development Server
```bash
# With auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production-like (no reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# With workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Health Checks
```bash
# Liveness
curl http://localhost:8000/health/live
# Expected: {"status":"alive"}

# Readiness
curl http://localhost:8000/health/ready
# Expected: {"status":"ready"}

# Root
curl http://localhost:8000/
# Expected: HTML with "Justice AI Agent"
```

### API Endpoints (Authenticated)
```bash
# Login (get token)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass"
# Response: {"access_token": "...", "token_type": "bearer", "tenant_id": "..."}

# Use token
TOKEN="<access_token>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/conversations

# Upload document
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.txt"

# List documents
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/documents

# Chat with skill
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "...", "message": "/skill wordcount {\"text\": \"hello world\"}"}'
```

---

## Testing Commands

```bash
# All tests
python -m pytest tests/ -v --tb=short

# Specific test file
python -m pytest tests/test_rag_service.py -v --tb=short

# Specific test function
python -m pytest tests/test_rag_service.py::test_rag_service -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

# Parallel (if pytest-xdist installed)
python -m pytest tests/ -n auto

# Verbose with output
python -m pytest tests/ -v -s --tb=long

# Stop on first failure
python -m pytest tests/ -x

# Run with specific markers
python -m pytest tests/ -m "not slow"
```

---

## Linting & Formatting

```bash
# Format with Black
black .

# Check formatting (CI)
black --check .

# Sort imports
isort .

# Check imports (CI)
isort --check-only .

# Lint with flake8
flake8 .

# Type check (optional)
mypy app/

# All checks (CI pipeline)
black --check . && isort --check-only . && flake8 .
```

---

## Docker Commands

```bash
# Build image
docker build -t justice-ai:latest .

# Run container
docker run -d \
  --name justice-ai \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/justice_ai \
  -e SECRET_KEY=your-secret \
  -e MODEL_PROVIDER=mock \
  justice-ai:latest

# View logs
docker logs -f justice-ai

# Stop & remove
docker stop justice-ai && docker rm justice-ai

# Execute command in container
docker exec -it justice-ai bash
```

---

## Git Commands

```bash
# Status
git status

# Add all
git add -A

# Commit (conventional)
git commit -m "feat(auth): add tenant_id to JWT claims"

# Push
git push origin feature/branch-name

# Pull latest main
git checkout main && git pull origin main

# Rebase feature onto main
git checkout feature/branch && git rebase main

# View history
git log --oneline -10

# Show diff
git diff
git diff --cached
```

---

## Environment Variables (.env)

```bash
# Required
DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/justice_ai
SECRET_KEY=your-256-bit-secret-key-here

# Optional (with defaults)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
MODEL_PROVIDER=mock
MODEL_NAME=mock-model
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
RAG_TOP_K=5
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
MAX_UPLOAD_SIZE=10485760
DEFAULT_TENANT_ID=default
```

---

## Troubleshooting Commands

```bash
# Check Python version
python --version

# Check installed packages
pip list

# Check port usage
netstat -ano | findstr :8000  # Windows
lsof -i :8000                  # Linux/macOS

# Kill process on port 8000
taskkill /PID <pid> /F         # Windows
kill -9 <pid>                  # Linux/macOS

# Reset database (dev only)
alembic downgrade base
alembic upgrade head

# Clear Python cache
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type d -name ".pytest_cache" -exec rm -rf {} +

# Reinstall dependencies
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

---

*All commands verified working as of 2026-10-20*
