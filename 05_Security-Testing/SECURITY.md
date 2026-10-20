# SECURITY.md — Security Requirements & Implementation

## Authentication

### JWT Tokens
- **Algorithm**: HS256
- **Expiry**: 30 minutes (configurable)
- **Claims**: `sub` (user_id), `tenant_id`, `exp`, `iat`
- **Secret**: `SECRET_KEY` env var (256-bit minimum)

### Password Handling
- **Hashing**: bcrypt via passlib (cost=12)
- **Verification**: Constant-time comparison
- **Policy**: Minimum 8 chars, recommended 12+

### Token Storage
- **Client**: HttpOnly Secure cookie OR Authorization header
- **Server**: No token storage (stateless)
- **Refresh**: Not implemented (re-login on expiry)

---

## Authorization

### Role-Based Access Control (RBAC)
| Role | Permissions | Description |
|------|-------------|-------------|
| `public` | (none) | Unauthenticated |
| `student` | `read` | Basic chat, document read |
| `lawyer` | `read,write` | Full chat, document CRUD |
| `admin` | `read,write,admin` | All + skill management |

### Permission Format
- Stored as CSV in `users.permissions`: `"read,write,admin"`
- Checked at skill execution time via `SkillRegistry`

### Skill Authorization
```python
# Skill declares required permissions
@skill_registry.register(
    name="admin_skill",
    required_permissions=["admin"]
)
def admin_skill(input: AdminInput) -> AdminOutput:
    ...

# Registry enforces at execution
def execute_skill(name, input_data, user):
    skill = get_skill(name)
    user_perms = user.permissions.split(",")
    if not all(p in user_perms for p in skill.required_permissions):
        raise PermissionError(...)
```

---

## Data Protection

### Tenant Isolation
- **Database**: `tenant_id` FK on ALL tables
- **Middleware**: JWT `tenant_id` → `ContextVar` → query filter
- **RAG**: Chunk retrieval scoped by `tenant_id` + `document_ids`
- **Zero cross-tenant leakage** verified in tests

### Encryption
| Data | At Rest | In Transit |
|------|---------|------------|
| Passwords | bcrypt hash | TLS 1.2+ |
| JWT | Signed (not encrypted) | TLS 1.2+ |
| Documents | File system | TLS 1.2+ |
| Embeddings | Plaintext (vector) | TLS 1.2+ |
| Database | Not encrypted | TLS 1.2+ |

### Secrets Management
- **Never commit**: `.env`, `.env.local`, `*.pem`, `*.key`
- **Use**: Environment variables only
- **CI/CD**: GitHub Actions secrets
- **Rotation**: Quarterly for `SECRET_KEY`

---

## Input Validation

### File Uploads
| Check | Implementation |
|-------|----------------|
| MIME type | Whitelist: `text/plain`, `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| Size | `MAX_UPLOAD_SIZE` (default 10MB) |
| Filename | `os.path.basename()` sanitization |
| Path traversal | `secure_filename()` equivalent |
| Content | Text extraction with error handling |

### API Input
- **Pydantic models** for all request bodies
- **FastAPI** automatic validation + 422 responses
- **SQLAlchemy** parameterized queries (no SQL injection)

---

## Rate Limiting (Planned)

### Implementation
- **Backend**: Redis sorted sets with sliding window
- **Key format**: `ratelimit:{tenant_id}:{ip}:{endpoint}`
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### Limits
| Tier | Requests | Window |
|-----|----------|--------|
| Auth | 10 | 1 min |
| Chat | 30 | 1 min |
| Upload | 20 | 1 min |
| Default | 100 | 1 min |

---

## Audit Logging (Planned)

### Events to Log
| Event | Fields |
|-------|--------|
| Login success/fail | user_id, tenant_id, ip, timestamp |
| Document upload | user_id, tenant_id, doc_id, filename |
| Skill execution | user_id, tenant_id, skill_name, success |
| Permission denied | user_id, tenant_id, resource, required_perms |
| Data export | user_id, tenant_id, scope |

### Retention
- **Security logs**: 1 year
- **Access logs**: 90 days
- **Debug logs**: 7 days

---

## Vulnerability Management

### Dependency Scanning
```bash
# Local
pip-audit

# CI/CD
github/codeql-action
dependabot alerts
```

### Container Security
- Base image: `python:3.12-slim`
- Non-root user: `appuser` (UID 1000)
- Read-only root filesystem (where possible)
- No unnecessary packages

---

## Incident Response

### Classification
| Severity | Response Time | Example |
|----------|---------------|---------|
| Critical | 1 hour | Active data breach, RCE |
| High | 4 hours | Auth bypass, data leak |
| Medium | 24 hours | XSS, CSRF |
| Low | 1 week | Info disclosure |

### Contacts
- **Security Lead**: [Configure in GitHub Security]
- **On-call**: [Configure in PagerDuty/Opsgenie]

---

## Compliance

### Data Retention
| Data Type | Retention | Deletion |
|-----------|-----------|----------|
| User accounts | Account lifetime + 30 days | On request / account deletion |
| Documents | Until user deletion | Cascade with user |
| Conversations | Until user deletion | Cascade with user |
| Audit logs | 1 year | Auto-purge |
| Embeddings | With parent document | Cascade with document |

### Privacy Rights
- **Access**: User can export all their data
- **Rectification**: Update via API
- **Erasure**: `DELETE /api/auth/me` (cascade)
- **Portability**: JSON export endpoint (planned)

---

## Security Testing

### Automated
```bash
# Dependency audit
pip-audit -r requirements.txt

# SAST
bandit -r app/

# Container
trivy image justice-ai:latest
```

### Manual (Quarterly)
- [ ] Penetration test (auth, RAG, file upload)
- [ ] Dependency review (outdated, vulnerable)
- [ ] Configuration audit (env vars, permissions)
- [ ] Log review (failed auth, permission denied)

---

## Security Contacts

- **Repository**: GitHub Security Advisories
- **Email**: [Configure in GitHub Settings > Security]
- **Responsible Disclosure**: [Link to SECURITY.md in repo root]

---

## Operating Modes and Security

### Mode A — Normal Operation
- External LLM used for primary reasoning; all security controls active

### Mode B — Fallback Operation  
- Security controls unchanged; fallback preserves tenant isolation
- No fabricated citations; evidence insufficiency stated explicitly

## Operating Modes and Security

### Mode A — Normal Operation (Large LLM Available)
- External LLM used for primary reasoning; all security controls active
- Tenant isolation enforced via JWT `tenant_id` claim
- All tool calls authorized through SkillRegistry permission checks
- RAG evidence scoped by tenant_id; no cross-tenant leakage
- External LLM API calls subject to rate limits and timeouts
- Fallback activates only after exhausting retry budget
- Debug/logging metadata privacy-aware; no sensitive data in logs

### Mode B — Fallback Operation (Large LLM Unavailable)
- All security controls persist unchanged from Mode A
- Authentication, authorization, tenant isolation active
- No tool execution bypass; same permission checks apply
- RAG evidence still scoped by tenant_id
- Response clearly states LLM unavailability
- No fabricated citations or sources
- Evidence insufficiency stated explicitly

### Security Critical Distinction
- Fallback is availability mechanism, NOT default inference strategy
- Security policies never relaxed regardless of mode
- Prompt injection protections active in both modes
- Unsafe retrieved content validated in both modes
- SSRF and URL injection protections active in both modes

*Security posture reviewed: 2026-10-20 — All Sprint 1 requirements met*
