# API-CONTRACTS.md — API Contracts & Endpoints

## Overview

RESTful API with JWT authentication. All endpoints require valid JWT except `/health/*` and `/`.

**Base URL**: `http://localhost:8000` (dev) / `https://api.justice-ai.com` (prod)

---

## Authentication

### Login
```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=testuser&password=testpass
```

**Response 200**:
```json
{
  "access_token": "<ACCESS_TOKEN>",
  "token_type": "bearer",
  "tenant_id": "712dd85e-398d-4890-a030-07f811bc159f"
}
```

**Response 401**: `{"detail": "Incorrect username or password"}`

### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "newuser",
  "email": "user@example.com",
  "password": "securepass123"
}
```

**Response 200**:
```json
{
  "id": "uuid",
  "username": "newuser",
  "email": "user@example.com",
  "tenant_id": "712dd85e-398d-4890-a030-07f811bc159f",
  "created_at": "2026-10-20T00:00:00Z"
}
```

### Token Usage
```http
Authorization: Bearer <access_token>
```

---

## Health Endpoints (No Auth)

### Liveness
```http
GET /health/live
```
**Response 200**: `{"status": "alive"}`

### Readiness
```http
GET /health/ready
```
**Response 200**: `{"status": "ready"}`

---

## Conversations

### List Conversations
```http
GET /api/conversations
Authorization: Bearer <token>
```

**Response 200**:
```json
[
  {
    "id": "uuid",
    "title": "Conversation Title",
    "created_at": "2026-10-20T00:00:00Z",
    "updated_at": "2026-10-20T00:00:00Z"
  }
]
```

### Create Conversation
```http
POST /api/conversations
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "New Conversation"
}
```

**Response 200**:
```json
{
  "id": "uuid",
  "title": "New Conversation",
  "created_at": "2026-10-20T00:00:00Z",
  "updated_at": "2026-10-20T00:00:00Z"
}
```

### Get Conversation
```http
GET /api/conversations/{conversation_id}
Authorization: Bearer <token>
```

### Delete Conversation
```http
DELETE /api/conversations/{conversation_id}
Authorization: Bearer <token>
```

---

## Messages

### Get Messages
```http
GET /api/conversations/{conversation_id}/messages
Authorization: Bearer <token>
```

**Response 200**:
```json
[
  {
    "id": "msg-uuid",
    "conversation_id": "uuid",
    "role": "user",
    "content": "Hello",
    "created_at": "2026-10-20T00:00:00Z"
  }
]
```

---

## Chat

### Send Message
```http
POST /api/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "conversation_id": "uuid",
  "message": "What does the document say about X?"
}
```

**Response 200** (with citations):
```json
{
  "response": "Based on the document...",
  "citations": [
    {
      "document_id": "uuid",
      "filename": "doc.txt",
      "chunk_index": 0,
      "chunk_text": "Relevant excerpt...",
      "similarity": 0.85
    }
  ]
}
```

### Skill Invocation
```http
POST /api/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "conversation_id": "uuid",
  "message": "/skill wordcount {\"text\": \"hello world\"}"
}
```

**Response 200**:
```json
{
  "response": "Skill wordcount result: {\"word_count\": 2}",
  "citations": []
}
```

---

## Documents

### Upload Document
```http
POST /api/documents/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <binary>
```

**Response 200**:
```json
{
  "id": "uuid",
  "filename": "document.pdf",
  "content_type": "application/pdf",
  "size": 102400,
  "created_at": "2026-10-20T00:00:00Z",
  "updated_at": null
}
```

**Supported types**: `text/plain`, `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

**Max size**: 10MB (configurable via `MAX_UPLOAD_SIZE`)

### List Documents
```http
GET /api/documents
Authorization: Bearer <token>
```

**Response 200**:
```json
[
  {
    "id": "uuid",
    "filename": "doc.pdf",
    "content_type": "application/pdf",
    "size": 102400,
    "created_at": "2026-10-20T00:00:00Z",
    "updated_at": null
  }
]
```

### Get Document
```http
GET /api/documents/{document_id}
Authorization: Bearer <token>
```

### Delete Document
```http
DELETE /api/documents/{document_id}
Authorization: Bearer <token>
```

---

## Skills

### List Skills
```http
GET /api/skills
Authorization: Bearer <token>
```

**Response 200**:
```json
{
  "skills": [
    {
      "name": "wordcount",
      "description": "Count words in text",
      "required_permissions": []
    }
  ]
}
```

### Execute Skill (Alternative to /chat)
```http
POST /api/skills/{skill_name}/execute
Authorization: Bearer <token>
Content-Type: application/json

{
  "text": "hello world"
}
```

---

## Error Responses

### 400 Bad Request
```json
{"detail": "Invalid input: field 'email' is required"}
```

### 401 Unauthorized
```json
{"detail": "Could not validate credentials"}
```

### 403 Forbidden
```json
{"detail": "Insufficient permissions for skill 'admin_skill'. Required: ['admin']"}
```

### 404 Not Found
```json
{"detail": "Conversation not found"}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "password"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Error
```json
{"detail": "Internal server error"}
```

---

## Rate Limiting (Planned)

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/api/auth/login` | 10 req | 1 min |
| `/api/chat` | 30 req | 1 min |
| `/api/documents/upload` | 20 req | 1 min |
| Default | 100 req | 1 min |

Headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1697800000
```

---

## Pagination (Planned)

### Query Parameters
```
?page=1&size=20
```

### Response
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "size": 20,
  "pages": 8
}
```

---

## WebSocket (Planned - Sprint 2)

### Streaming Chat
```http
GET /api/chat/stream?conversation_id=...
Authorization: Bearer <token>
Upgrade: websocket
```

### Message Format
```json
{"type": "token", "content": "Hello"}
{"type": "citation", "citations": [...]}
{"type": "done"}
```

---

## Versioning

| Version | Status | Date |
|---------|--------|------|
| v1 | Current | 2026-10-20 |

**Breaking changes** require new version prefix: `/api/v2/...`

---

*All endpoints verified with test suite (19 tests passing)*
