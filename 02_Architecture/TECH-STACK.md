# TECH-STACK.md — Technology Stack

## Core Runtime

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.12+ | Primary language |
| FastAPI | 0.133.1 | Async web framework |
| Uvicorn | 0.41.0 | ASGI server |
| Pydantic | 2.13.4 | Data validation & settings |

## Database & ORM

| Component | Version | Purpose |
|-----------|---------|---------|
| PostgreSQL | 18.6 | Primary database |
| pgvector | 0.5.1 | Vector similarity search |
| SQLAlchemy | 2.1.4 | ORM (2.0 style) |
| Alembic | 1.13.1 | Database migrations |
| psycopg | 3.3.6 | PostgreSQL driver (binary) |

## Authentication & Security

| Component | Version | Purpose |
|-----------|---------|---------|
| PyJWT | 2.13.0 | JWT token handling |
| python-jose | 3.3.0 | JOSE/JWT utilities |
| passlib | 1.7.4 | Password hashing abstraction |
| bcrypt | 3.2.0 | Bcrypt implementation |

## AI / ML

| Component | Version | Purpose |
|-----------|---------|---------|
| sentence-transformers | 6.1.0 | Embedding generation |
| huggingface-hub | 1.24.0 | Model downloads |
| torch | 2.14.0 | Backend for transformers |
| transformers | 5.17.0 | Model architectures |
| scikit-learn | 1.9.1 | Similarity utilities |

## Document Processing

| Component | Version | Purpose |
|-----------|---------|---------|
| PyPDF2 | 3.0.1 | PDF text extraction |
| python-docx | 1.1.0 | DOCX text extraction |
| python-multipart | 0.0.32 | File upload handling |

## Caching & Infrastructure

| Component | Version | Purpose |
|-----------|---------|---------|
| Redis | 7.x (server) | Session cache, rate limiting |
| redis-py | 5.x | Redis client |

## Testing

| Component | Version | Purpose |
|-----------|---------|---------|
| pytest | 9.1.1 | Test framework |
| pytest-asyncio | 1.4.0 | Async test support |

## Development Tools

| Component | Version | Purpose |
|-----------|---------|---------|
| black | latest | Code formatting |
| isort | latest | Import sorting |
| flake8 | latest | Linting |
| mypy | latest | Type checking |

## Container & Deployment

| Component | Version | Purpose |
|-----------|---------|---------|
| Docker | 24+ | Containerization |
| docker-compose | 2+ | Local orchestration |

## Version Pinning Policy

- **Exact versions** for all dependencies (`==`)
- **No floating versions** (`>=`, `~=`, `*`)
- **Update via PR** with test verification
- **Security patches** prioritized

## Compatibility Matrix

| Python | FastAPI | SQLAlchemy | Pydantic | pgvector |
|--------|---------|------------|----------|----------|
| 3.12+ | 0.133.1 | 2.1.4 | 2.13.4 | 0.5.1 |

## License Summary

| Package | License |
|---------|---------|
| FastAPI | MIT |
| SQLAlchemy | MIT |
| pgvector | MIT |
| sentence-transformers | Apache-2.0 |
| PyJWT | MIT |
| passlib | BSD |
| bcrypt | Apache-2.0 |

---

*All versions pinned in `requirements.txt`. Update via Dependabot PR or manual review.*
