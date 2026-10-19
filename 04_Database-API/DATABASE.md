# DATABASE.md — Database Schema & Conventions

## Overview

PostgreSQL 18.6 with pgvector extension for vector similarity search.
All tables are multi-tenant with `tenant_id` foreign key to `tenants` table.

---

## Tables

### tenants
```sql
CREATE TABLE tenants (
    id VARCHAR PRIMARY KEY,           -- UUID
    name VARCHAR NOT NULL UNIQUE,     -- slug identifier
    display_name VARCHAR,             -- human-readable
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    settings TEXT,                    -- JSON string
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);
```

**Indexes**: Primary key on `id`, unique on `name`

**Default tenant**: `712dd85e-398d-4890-a030-07f811bc159f` (name: `default`)

---

### users
```sql
CREATE TABLE users (
    id VARCHAR PRIMARY KEY,           -- UUID
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    username VARCHAR NOT NULL UNIQUE,
    email VARCHAR NOT NULL UNIQUE,
    hashed_password VARCHAR NOT NULL, -- bcrypt
    is_active BOOLEAN DEFAULT true,
    permissions VARCHAR DEFAULT '',   -- CSV: "admin,lawyer"
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);
```

**Indexes**: PK on `id`, unique on `username`, `email`, FK on `tenant_id`

**Permissions format**: Comma-separated (e.g., `"admin,lawyer,student"`)

---

### documents
```sql
CREATE TABLE documents (
    id VARCHAR PRIMARY KEY,           -- UUID
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    user_id VARCHAR NOT NULL REFERENCES users(id),
    filename VARCHAR NOT NULL,
    content_type VARCHAR NOT NULL,    -- MIME type
    size INTEGER NOT NULL,            -- bytes
    storage_path VARCHAR NOT NULL,    -- relative to uploads/
    extracted_text TEXT,              -- full extracted text
    processing_status VARCHAR DEFAULT 'pending', -- pending/processing/completed/failed
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);
```

**Indexes**: PK on `id`, FK on `tenant_id`, `user_id`

---

### document_chunks
```sql
CREATE TABLE document_chunks (
    id VARCHAR PRIMARY KEY,           -- format: {doc_id}-chunk-{index}
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    document_id VARCHAR NOT NULL REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(384),            -- pgvector type
    chunk_metadata TEXT,              -- JSON string
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Indexes**: PK on `id`, FK on `tenant_id`, `document_id`

**Vector search**: Uses `embedding <-> query_vector` (cosine distance)

---

### conversations
```sql
CREATE TABLE conversations (
    id VARCHAR PRIMARY KEY,           -- UUID
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    user_id VARCHAR NOT NULL REFERENCES users(id),
    title VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);
```

**Indexes**: PK on `id`, FK on `tenant_id`, `user_id`

---

### messages
```sql
CREATE TABLE messages (
    id VARCHAR PRIMARY KEY,           -- format: msg-{conv_id}-{index}-{role}
    tenant_id VARCHAR NOT NULL REFERENCES tenants(id),
    conversation_id VARCHAR NOT NULL REFERENCES conversations(id),
    role VARCHAR NOT NULL,            -- user/assistant/system
    content TEXT NOT NULL,
    provider_metadata TEXT,           -- JSON string
    token_usage TEXT,                 -- JSON string
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Indexes**: PK on `id`, FK on `tenant_id`, `conversation_id`

---

### alembic_version
```sql
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);
```

---

## Multi-Tenancy Enforcement

### Schema Level
- Every table has `tenant_id` NOT NULL FK to `tenants.id`
- No table is tenant-agnostic

### Application Level
1. **Middleware** extracts `tenant_id` from JWT to `ContextVar`
2. **Routers** require `Depends(get_current_tenant_id)`
3. **Services** scope all queries by `tenant_id`
4. **RAG** filters chunks by `tenant_id` AND `document_ids`

### Query Pattern
```python
# ALWAYS include tenant_id
db.query(Model).filter(
    Model.tenant_id == get_current_tenant_id(),
    Model.user_id == user_id
)
```

---

## Vector Search (pgvector)

### Embedding Storage
```sql
-- Column definition
embedding VECTOR(384)  -- 384 dimensions for all-MiniLM-L6-v2
```

### Similarity Query
```sql
-- Cosine distance (lower = more similar)
SELECT id, chunk_text, embedding <-> $1 AS distance
FROM document_chunks
WHERE tenant_id = $2
  AND document_id IN ($3, $4, $5)
ORDER BY embedding <-> $1
LIMIT 5;
```

### Index (Optional for Scale)
```sql
-- HNSW index for approximate nearest neighbor
CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

---

## JSON Columns Convention

### Storage
- Store as `TEXT` column
- Serialize with `json.dumps()`
- Deserialize with `json.loads()`

### Examples
```python
# chunk_metadata
json.dumps({
    "page": 1,
    "section": "Introduction",
    "source": "pdf"
})

# provider_metadata (messages)
json.dumps({
    "model": "mock-model",
    "finish_reason": "stop"
})

# token_usage (messages)
json.dumps({
    "prompt_tokens": 150,
    "completion_tokens": 75,
    "total_tokens": 225
})
```

---

## Migration Conventions

### Naming
```
alembic/versions/
├── 93541014bf64_initial_migration_with_tenant_id_and_pgvector.py
├── a1b2c3d4e5f6_add_message_tenant_id.py
└── ...
```

### Template
```python
# revision: 'a1b2c3d4e5f6'
# down_revision: '93541014bf64'
# branch_labels: None
# depends_on: None

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

def upgrade():
    op.add_column('messages', sa.Column('tenant_id', sa.String(), nullable=False))
    op.create_foreign_key('fk_messages_tenant', 'messages', 'tenants', ['tenant_id'], ['id'])

def downgrade():
    op.drop_constraint('fk_messages_tenant', 'messages', type_='foreignkey')
    op.drop_column('messages', 'tenant_id')
```

---

## Connection Configuration

### SQLAlchemy Engine
```python
# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

def get_connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=get_connect_args(settings.DATABASE_URL),
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### Environment Variables
```bash
# .env
DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/justice_ai
```

---

## Backup & Recovery

### Logical Backup
```bash
# Full backup
pg_dump -h 127.0.0.1 -U postgres -d justice_ai > backup_$(date +%Y%m%d).sql

# Schema only
pg_dump -h 127.0.0.1 -U postgres -d justice_ai --schema-only > schema.sql

# Data only
pg_dump -h 127.0.0.1 -U postgres -d justice_ai --data-only > data.sql
```

### Restore
```bash
psql -h 127.0.0.1 -U postgres -d justice_ai < backup_20261020.sql
```

---

## Performance Tuning

### PostgreSQL Settings (postgresql.conf)
```ini
# For vector workloads
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 64MB
maintenance_work_mem = 256MB
max_parallel_workers_per_gather = 4

# pgvector HNSW
max_parallel_maintenance_workers = 4
```

### Connection Pooling
```python
# In production, use PgBouncer
# SQLAlchemy pool settings
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

---

*Schema verified against running PostgreSQL 18.6 with pgvector 0.5.1*