# ARCHITECTURE.md — System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTS                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Web UI      │  │ API Clients │  │ Internal Services       │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
          ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI APPLICATION                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ Routers      │ │ Middleware   │ │ Dependencies │             │
│  │ /auth        │ │ AuthMiddleware│ │ get_db       │             │
│  │ /documents   │ │ TenantContext │ │ get_current_user│            │
│  │ /conversations│ │              │ │ get_tenant_id │             │
│  │ /chat        │ │              │ │              │             │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘             │
└─────────┼────────────────┼─────────────────┼────────────────────┘
          │                │                 │
          ▼                ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SERVICES LAYER                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ AuthService  │ │ DocumentSvc  │ │ ChatService  │             │
│  │ - register   │ │ - upload     │ │ - generate   │             │
│  │ - login      │ │ - list/delete│ │ - skills     │             │
│  │ - get_tenant │ │ - extract    │ │ - RAG flow   │             │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘             │
│         │                │                 │                     │
│  ┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐             │
│  │ RAGService   │ │ ConvService  │ │ SkillRegistry│             │
│  │ - chunk      │ │ - CRUD       │ │ - register   │             │
│  │ - embed      │ │ - list       │ │ - execute    │             │
│  │ - search     │ │              │ │ - authorize  │             │
│  └──────┬───────┘ └──────────────┘ └──────────────┘             │
└─────────┼────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                 │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │ PostgreSQL 18.6  │    │ Redis 7.x        │                   │
│  │ + pgvector       │    │ (sessions, rate) │                   │
│  │                  │    │                  │                   │
│  │ Tables:          │    │ Keys:            │                   │
│  │ - tenants        │    │ - session:*      │                   │
│  │ - users          │    │ - ratelimit:*    │                   │
│  │ - conversations  │    │ - cache:*        │                   │
│  │ - messages       │    │                  │                   │
│  │ - documents      │    │                  │                   │
│  │ - document_chunks│    │                  │                   │
│  │   (embedding VEC)│    │                  │                   │
│  └──────────────────┘    └──────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

## Multi-Tenant Data Model

All tables include `tenant_id` (FK → `tenants.id`):

```
tenants
  ├── id (PK)
  ├── name (unique)
  ├── display_name
  ├── description
  ├── is_active
  ├── settings (JSON)
  └── timestamps

users
  ├── id (PK)
  ├── tenant_id (FK, NOT NULL)  ◄─── Multi-tenant isolation
  ├── username (unique)
  ├── email (unique)
  ├── hashed_password
  ├── is_active
  ├── permissions (CSV: "admin,lawyer")
  └── timestamps

documents
  ├── id (PK)
  ├── tenant_id (FK, NOT NULL)
  ├── user_id (FK)
  ├── filename, content_type, size
  ├── storage_path, extracted_text
  ├── processing_status
  └── timestamps

document_chunks
  ├── id (PK)
  ├── tenant_id (FK, NOT NULL)  ◄─── Direct filter for RAG
  ├── document_id (FK)
  ├── chunk_index, chunk_text
  ├── embedding VECTOR(384)     ◄─── pgvector column
  ├── chunk_metadata (JSON text)
  └── created_at

conversations
  ├── id (PK)
  ├── tenant_id (FK, NOT NULL)
  ├── user_id (FK)
  ├── title
  └── timestamps

messages
  ├── id (PK)
  ├── tenant_id (FK, NOT NULL)  ◄─── Required for audit
  ├── conversation_id (FK)
  ├── role (user/assistant/system)
  ├── content
  ├── provider_metadata (JSON)
  ├── token_usage (JSON)
  └── created_at
```

## Tenant Isolation Mechanism

### ContextVar Pattern (Request-Scoped)

```python
# app/core/security.py
tenant_id_var: ContextVar[str] = ContextVar("tenant_id")

# Middleware extracts from JWT
async def tenant_middleware(request: Request, call_next):
    token = extract_token(request)
    if token:
        claims = decode_jwt(token)
        tenant_id_var.set(claims.get("tenant_id", "default"))
    try:
        return await call_next(request)
    finally:
        tenant_id_var.reset()
```

### Usage in Services

```python
# Automatic scoping via ContextVar
def get_current_tenant_id() -> str:
    return tenant_id_var.get("default")

# All queries implicitly scoped
db.query(Document).filter(Document.tenant_id == get_current_tenant_id())
```

### Enforcement Points

| Layer | Mechanism |
|-------|-----------|
| Router | `Depends(get_current_tenant_id)` on all endpoints |
| Service | `tenant_id` passed explicitly or via ContextVar |
| RAG | `retrieve_relevant_chunks(..., tenant_id=...)` |
| Skill | User object carries tenant via relationship |

## RAG Pipeline

```
Document Upload
      │
      ▼
┌─────────────────┐
│ Text Extraction │  (PyPDF2 / python-docx / TXT)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Chunking        │  (size=1000, overlap=200, sentence-aware)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Embedding       │  (sentence-transformers: all-MiniLM-L6-v2)
│ Generation      │  → 384-dim vector
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ pgvector Store  │  INSERT INTO document_chunks (embedding, ...)
│ (Vector(384))   │  WITH tenant_id, document_id
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Query Time      │
│ 1. Embed query  │
│ 2. Cosine sim   │  SELECT *, embedding <-> query_vec AS dist
│ 3. Filter by    │  FROM document_chunks
│    tenant_id    │  WHERE tenant_id = $1
│    document_ids │    AND document_id IN (...)
│ 4. Top-k + cite │  ORDER BY dist LIMIT $k
└─────────────────┘
```

## Skill System Architecture

```
┌────────────────────────────────────┐
│ SkillRegistry (singleton)          │
│ - register(skill: Skill)           │
│ - get_skill(name) → Skill          │
│ - execute_skill(name, input, user) │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ Skill (dataclass)                  │
│ - name, description                │
│ - input_model: SkillInput (Pydantic)│
│ - output_model: SkillOutput        │
│ - func: Callable[[Input], Output]  │
│ - required_permissions: List[str]  │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ Authorization Check                │
│ if skill.required_permissions:     │
│   user_perms = user.permissions.split(',')│
│   if not all(p in user_perms for p in skill.required_permissions):│
│       raise PermissionError(...)   │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ Execution                          │
│ result = skill.func(input)         │
│ return skill.output_model(**result)│
└────────────────────────────────────┘
```

## Configuration

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| Database | `DATABASE_URL` | `postgresql://postgres@127.0.0.1:5432/justice_ai` | PostgreSQL connection |
| JWT Secret | `SECRET_KEY` | **required** | HS256 signing key |
| JWT Algorithm | `ALGORITHM` | `HS256` | Token algorithm |
| Token Expiry | `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Minutes |
| Model Provider | `MODEL_PROVIDER` | `mock` | `mock` \| `openai` \| `anthropic` |
| Embedding Provider | `EMBEDDING_PROVIDER` | `sentence-transformers` | `mock` \| `sentence-transformers` |
| Embedding Model | `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | HF model ID |
| Embedding Dim | `EMBEDDING_DIMENSIONS` | `384` | Vector size |
| RAG Top-K | `RAG_TOP_K` | `5` | Retrieval limit |
| Chunk Size | `CHUNK_SIZE` | `1000` | Characters |
| Chunk Overlap | `CHUNK_OVERLAP` | `200` | Characters |
| Max Upload | `MAX_UPLOAD_SIZE` | `10485760` | 10 MB |
| Default Tenant | `DEFAULT_TENANT_ID` | `default` | Fallback tenant |

## Security Considerations

| Area | Implementation |
|------|----------------|
| Passwords | bcrypt via passlib (cost=12 default) |
| JWT | HS256, 30-min expiry, `tenant_id` claim |
| SQL Injection | SQLAlchemy ORM (parameterized queries) |
| File Upload | Sanitized filenames, type validation, size limit |
| Path Traversal | `os.path.basename`, secure upload dir |
| Rate Limiting | Redis-based (planned, key: `ratelimit:{tenant}:{ip}`) |
| CORS | Configured via FastAPI middleware |

## Sprint 2 Architecture Preview (LangGraph)

```
┌─────────────────────────────────────────────────────────────┐
│ LangGraph Orchestration Layer                                │
│                                                             │
│  State: { messages, context, citations, tenant_id, ... }   │
│                                                             │
│  Nodes:                                                     │
│  ├── retrieve_context(query, tenant_id) → chunks           │
│  ├── generate_response(history, context) → response        │
│  ├── invoke_skill(skill_name, args, user) → result         │
│  └── finalize(citations, metadata) → output                │
│                                                             │
│  Checkpointing: PostgresSaver                               │
│  - checkpoint_ns = f"tenant_{tenant_id}"                   │
│  - Thread ID = conversation_id                              │
│  - Zero cross-tenant leakage                                │
└─────────────────────────────────────────────────────────────┘
```

---

*See also: Obsidian `14-Architecture-Synthesis/Justice-AI-Architecture-Implications.md` and ADRs in `00-Home/`