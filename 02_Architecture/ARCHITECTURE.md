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


==================================================
1. THE NON-NEGOTIABLE PRODUCT ARCHITECTURE
==================================================

Justice AI is a law-focused AI agent.

Its normal operating mode MUST use a configured external large LLM API
for deeper reasoning, analysis of retrieved evidence, and final answer
generation.

Lightweight models are internal supporting capabilities of Justice AI.
They help understand queries, classify intent, prepare searches, support
retrieval, select or prepare tool calls, and perform bounded verification
tasks.

They are not the default replacement for the external large LLM.

The intended design has TWO operating modes.

MODE A — NORMAL OPERATION: LARGE LLM AVAILABLE

1. Receive the user request.
2. Authenticate and authorize the user.
3. Establish the correct tenant and conversation context.
4. Validate the input and apply security controls.
5. Use a lightweight internal model or deterministic logic to understand
   the query, classify its intent, identify the legal domain and jurisdiction,
   extract relevant facts, and identify missing information.
6. Use the orchestrator to prepare an appropriate research plan.
7. Determine which RAG collections, database queries, approved web searches,
   legal research tools, and other authorized tools are required.
8. Retrieve relevant information and collect supporting evidence.
9. Validate source metadata and rank the evidence.
10. Send the original question, interpreted intent, relevant context, and
    collected evidence to the configured external large LLM API.
11. Let the large LLM perform the primary legal reasoning and produce the
    draft answer.
12. Use lightweight models and/or deterministic validators for bounded
    critique tasks, such as checking whether claims are supported, citations
    correspond to retrieved sources, or required information is missing.
13. If the critique identifies a material problem, return the findings and
    relevant evidence to the large LLM for revision when the API remains
    available and the configured retry budget permits it.
14. Validate the final answer, citations, permissions, and output format.
15. Return the answer with appropriate citations, limitations, and uncertainty.
16. Record privacy-aware operational metadata for debugging and evaluation.

The orchestrator must use task-dependent routing. Do not blindly invoke
every tool or every model for every query.

Tool execution must remain controlled by deterministic permissions and
authorization checks. An LLM proposal alone does not authorize a tool call.

The large LLM is the primary reasoning and answer-generation engine.
Lightweight models support the workflow.

MODE B — FALLBACK OPERATION: LARGE LLM UNAVAILABLE

If the external LLM is not configured or is unavailable after permitted
retries, Justice AI must switch to a clearly identified fallback workflow.

1. Continue authenticating and authorizing the user normally.
2. Use available lightweight components to understand the query.
3. Search the authorized internal database, RAG collections, indexed
   documents, and other configured information sources.
4. Use approved web-search or legal-research tools only when configured,
   available, and authorized.
5. Rank and validate the retrieved evidence.
6. Produce a limited evidence-based response using an available local model
   or deterministic formatting and extraction logic.
7. Include citations and source metadata wherever available.
8. Clearly state that full external-LLM reasoning was unavailable when this
   materially affects the response.
9. Identify missing evidence and uncertainty.
10. Do not fabricate research, citations, sources, API results, or claims
    that a tool or model was successfully called.
11. Do not imply that the fallback response has undergone the same reasoning
    process as a normal large-LLM response.

If the evidence is insufficient, say so instead of inventing a legal answer.

Fallback mode must not bypass authentication, tenant isolation, security
checks, source validation, or output policies.

IMPORTANT DISTINCTION:
The fallback is an availability mechanism, not the default inference strategy.

==================================================
2. DEFINE THE INTERNAL LIGHTWEIGHT MODEL LAYER
==================================================

Document lightweight models as internal capabilities managed by Justice AI.

Potential responsibilities include:

- Query intent and legal-domain classification.
- Jurisdiction and entity extraction.
- Query rewriting and search-query generation.
- Retrieval planning and evidence ranking.
- Document classification and extraction.
- Citation-to-source matching.
- Bounded critique and missing-evidence detection.
- Fallback response organization.

These are logical responsibilities, not a requirement to deploy one separate
model per task.

Use deterministic code when it is sufficient. Use local models where their
accuracy, latency, resource use, and licensing make sense.

For each proposed model task, document:
- Input and output schemas.
- Why a model is needed.
- Whether deterministic code could do the job.
- Expected resource requirements.
- Failure behavior.
- Validation requirements.
- Relevant tests.
- Implementation status.

Do not assume that lightweight models are always correct. Their outputs
must be validated and must not independently grant permissions or override
security rules.

Do not download models or change dependencies during this documentation
task.

==================================================
3. DEFINE THE EXTERNAL LARGE LLM LAYER
==================================================

The external large LLM is responsible for primary reasoning over the user's
question, relevant conversation context, and retrieved evidence.

Document a provider-independent interface that allows the provider or model
to be changed without rewriting the orchestration logic.

Include:
- Provider and model configuration.
- Environment variables.
- API-key handling.
- Structured request and response schemas.
- Timeouts.
- Bounded retries.
- Rate limits.
- Provider errors.
- Streaming, if supported by the existing application.
- Token and cost tracking.
- Observability without sensitive-data leakage.
- Mock-provider testing.
- Fallback activation.
- Recovery from fallback to normal operation.

Do not make paid API calls or connect a real provider during this task.
We will configure and connect the provider in a later phase.

A successful HTTP request alone does not prove the generated legal answer
is correct. Answer quality must be evaluated separately.

==================================================
4. RAG, DATABASE AND EXTERNAL RESEARCH
==================================================

Document the complete retrieval pipeline.

Potential sources:
- PostgreSQL and pgvector.
- Authorized user documents.
- Internal legal knowledge collections.
- Indexed statutes, regulations, judgments, and other approved legal sources.
- Configured web-search tools.
- Other explicitly approved research tools.

Inspect the actual code before deciding which sources already work.

Document:
- Ingestion and document processing.
- Chunking and metadata.
- Embedding generation.
- Vector and keyword retrieval, where implemented.
- Metadata and jurisdiction filtering.
- Relevance ranking.
- Deduplication.
- Source reliability.
- Dates and legal status.
- Citation metadata.
- Retrieval failure handling.
- Tenant isolation.
- Indexing and update strategy.

Do not assume that PostgreSQL, pgvector, or a particular retrieval technique
has been correctly implemented without inspecting the actual schema and code.

RAG is used in both normal and fallback modes.

In normal mode, RAG and research tools supply evidence to the large LLM.
In fallback mode, available evidence supplies the foundation for a limited
local response.

Do not claim that web search works unless the corresponding tool exists,
is configured, and has been tested.

==================================================
5. TOOL-CALLING ARCHITECTURE
==================================================

Document how the agent selects, validates, and executes tools.

For every tool, specify:
- Purpose.
- Input and output schemas.
- Authorization requirements.
- Data access boundaries.
- Validation.
- Timeout and retry behavior.
- Failure handling.
- Audit requirements.
- Tests.
- Whether implemented or planned.

The lightweight model may help classify the query and prepare a proposed
tool plan. The orchestrator validates that plan and authorizes execution.

The large LLM should receive useful tool results and may request further
research through the controlled orchestration process.

Do not allow unrestricted execution of arbitrary commands, SQL, URLs,
browser actions, or external tools.

Treat uploaded documents and retrieved content as untrusted input.

==================================================
6. CRITIQUE AND REVISION
==================================================

The normal workflow must allow the large LLM to produce a draft, followed
by appropriate independent checks.

Document how the system checks:
- Claim-to-source support.
- Citation correspondence.
- Jurisdiction.
- Missing material facts.
- Contradictions.
- Outdated or potentially superseded sources.
- Unsupported certainty.
- Output-schema compliance.

Distinguish deterministic validation from model-based critique.

A critique model must not be treated as a legal authority or a guarantee
of correctness.

Specify:
- What constitutes a material failure.
- Whether retrieval should be repeated.
- When the large LLM should revise the answer.
- Maximum revision attempts.
- What happens when the critique and generator disagree.
- What happens when the LLM API fails during revision.
- When to return a limited response or state that evidence is insufficient.

Avoid endless critique loops.

==================================================
7. ORCHESTRATION AND STATE MANAGEMENT
==================================================

Inspect the existing implementation and approved architecture decisions.

Use LangGraph if it remains the approved orchestration framework.

Document explicit states and conditional transitions for:
- Request validation.
- Query understanding.
- Research planning.
- Tool selection and authorization.
- Retrieval.
- Evidence validation.
- External LLM generation.
- Critique.
- Revision.
- Final validation.
- Fallback.
- Error handling.
- Completion.

Specify typed state fields, ownership, permitted transitions, persistence,
checkpointing, and tenant-safe conversation identifiers.

Make the difference between normal and fallback paths explicit.

Ensure that provider failures lead to bounded retries and a deliberate
fallback decision rather than infinite retries or silent mock responses.

Do not implement speculative graph nodes merely to make a diagram look complete.

==================================================
8. COMPLETE ALL EXISTING MARKDOWN DOCUMENTATION
==================================================

Inspect and correct the existing documentation in place.

At minimum review:
- AGENTS.md.
- PROJECT.md.
- PROJECT-STATE.md.
- ARCHITECTURE.md.
- TECH-STACK.md.
- WORKFLOW.md.
- CODING-STANDARDS.md.
- COMMANDS.md.
- DATABASE.md.
- API-CONTRACTS.md.
- SECURITY.md.
- TESTING.md.
- DEPLOYMENT.md.
- DECISIONS.md and individual ADRs.
- KNOWN-ISSUES.md.
- CHANGELOG.md.
- Sprint roadmap and checklists.

Also create or update dedicated documents for model architecture, LLM providers,
local models, RAG/retrieval, and tool calling only where these add distinct
value and do not duplicate existing content.

For every document:
1. Define its purpose.
2. Add detailed engineering instructions.
3. Cross-link related documentation.
4. Separate actual implementation from planned behavior.
5. Identify unresolved decisions.
6. Verify commands, paths, dependencies, endpoints, and configuration names.
7. Avoid unsupported claims and duplicated content.

AGENTS.md must tell every coding agent how to navigate the documentation,
inspect code, make incremental changes, run checks, update state, and report
evidence.

PROJECT-STATE.md must remain concise and accurate.

ARCHITECTURE.md must explain both operating modes.

TESTING.md must define tests for normal operation, API failures, fallback,
tool execution, RAG, citation checks, security, and recovery.

SECURITY.md must cover authentication, authorization, tenant isolation,
prompt injection, unsafe retrieved content, SSRF, secrets, and tool permissions.

DATABASE.md must match the actual schema and migrations.

DEPLOYMENT.md must match the actual local and deployment environments.

==================================================
9. ENGINEERING WORKFLOW AND VERIFICATION
==================================================

Document a practical workflow that coding agents must follow:

1. Read AGENTS.md and PROJECT-STATE.md.
2. Read the relevant architecture and component documentation.
3. Inspect the existing implementation and Git status.
4. Identify the exact requirement and acceptance criteria.
5. Trace the relevant code and data flow.
6. Plan a small, reviewable change.
7. Implement incrementally.
8. Run syntax and import checks.
9. Run focused unit tests.
10. Run integration tests for affected components.
11. Run relevant database and migration tests.
12. Run security and regression tests.
13. Run the full relevant test suite.
14. Run linting and type checks where configured.
15. Inspect the Git diff and check for secrets.
16. Update documentation and project state.
17. Verify the actual results before reporting completion.

Explain how to investigate syntax errors, import failures, schema mismatches,
API errors, database migration problems, test failures, and runtime failures.

Use the real project commands. Do not invent commands or report checks as
successful when they were not executed.

==================================================
10. SECURITY, DATABASE, TESTING AND DEPLOYMENT
==================================================

Make the documentation suitable for experienced engineers responsible for
each discipline.

DATABASE:
Actual schema, relationships, migrations, tenant isolation, document metadata,
embeddings, conversations, messages, checkpointing where implemented,
indexes, transactions, backups, recovery, and retention.

SECURITY:
Threat model, authentication, authorization, tenant isolation, secrets,
input validation, malicious documents, prompt injection, retrieval poisoning,
tool permissions, SSRF, rate limiting, privacy, audit logs, and incident response.

TESTING:
Syntax checks, unit tests, integration tests, end-to-end tests, security tests,
provider failure tests, fallback tests, citation evaluation, legal QA, regression,
performance, and CI acceptance criteria.

DEPLOYMENT:
Environment setup, configuration, database provisioning, migrations, CI/CD,
secrets, health checks, monitoring, rollback, backups, recovery, and production
verification.

Separate implemented controls from planned controls.

Do not install Docker or reinstall PostgreSQL. Do not modify the database,
delete data, or download large models.

==================================================
11. CURRENT STATE, OBSIDIAN AND CHANGE CONTROL
==================================================

Inspect the actual Git repository, Markdown files, code, tests, CI, and relevant
Obsidian notes before editing.

Use the evidence statuses:
IMPLEMENTED, TESTED, VERIFIED OPERATIONALLY, PARTIALLY IMPLEMENTED,
PLANNED, BLOCKED, and UNVERIFIED.

Synchronize existing Obsidian roadmap, sprint checklist, and decision log
without creating duplicates.

Preserve unrelated changes and Git history.

Do not make paid LLM API calls, expose secrets, reset the database, force-push,
or rewrite application code during this documentation task.

Make documentation changes in place and validate links, paths, diagrams,
and consistency with implementation.

If a code or dependency change appears necessary, identify the blocker and
proposed minimal change rather than silently expanding the scope.

==================================================
12. FINAL REPORT
==================================================

Report:
- Files inspected and changed.
- Documentation gaps corrected.
- Confirmed implementation versus planned architecture.
- Normal-mode workflow.
- Fallback-mode workflow.
- Lightweight-model responsibilities.
- External LLM API interface design.
- RAG, database, and tool-calling design.
- Critique and revision behavior.
- Security, testing, and deployment documentation.
- Obsidian files updated.
- Validation commands actually executed and their results.
- Outstanding decisions and blockers.
- Recommended next implementation task.

Use evidence from actual files, diffs, tests, and CI results.

Do not claim production readiness simply because the documentation is complete.

START:
Inspect the actual project and existing documentation, correct the architecture
to match the two operating modes above, update the relevant Markdown files in
place, validate the changes, and report exactly what is complete.
