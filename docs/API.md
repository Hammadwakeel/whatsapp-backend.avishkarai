# Inika Backend API Documentation

## Overview

Multi-Tenant Hotel Platform with WhatsApp AI Agent integration.

- **Framework**: FastAPI (async)
- **Database**: PostgreSQL with async SQLAlchemy
- **Auth**: JWT (access + refresh tokens) with tenant_id
- **Architecture**: Multi-tenant (each hotel = tenant)
- **API Keys**: SHARED across all tenants (OpenRouter, Tavily)
- **Port**: 8000

---

## Table of Contents

1. [Authentication](#authentication) - Tenant-based auth (register, login, logout)
2. [Profile](#profile) - Tenant profile management
3. [Wiki](#wiki) - Knowledge base API
4. [Agent Configuration](#agent-configuration) - AI agent configuration
5. [Health](#health) - Health check endpoints
6. [Data Models](#data-models)
7. [Error Responses](#error-responses)

---

## Authentication

### Register Tenant (Hotel Admin)

Create a new hotel tenant account.

**Endpoint**: `POST /auth/register`

**Request Body**:
```json
{
  "name": "Hotel Paradise",
  "email": "admin@hotel.com",
  "password": "SecurePass123!",
  "phone": "+1234567890",
  "hotel_name": "Hotel Paradise",
  "hotel_address": "123 Beach Road, Miami"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Hotel admin name |
| email | string | Yes | Valid email, unique across all tenants |
| password | string | Yes | Minimum 8 characters |
| phone | string | No | Contact phone number |
| hotel_name | string | No | Hotel name |
| hotel_address | string | No | Hotel address |

**Response** (201 Created):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "tenant": {
    "id": "uuid",
    "name": "Hotel Paradise",
    "email": "admin@hotel.com",
    "hotel_name": "Hotel Paradise",
    "hotel_address": "123 Beach Road, Miami",
    "phone": "+1234567890",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

**Errors**:
- `400`: Email already registered
- `422`: Validation error

---

### Login

Authenticate as tenant (hotel admin) and receive tokens.

**Endpoint**: `POST /auth/login`

**Request Body**:
```json
{
  "email": "admin@hotel.com",
  "password": "SecurePass123!"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "tenant": {
    "id": "uuid",
    "name": "Hotel Paradise",
    "email": "admin@hotel.com",
    ...
  }
}
```

**JWT Payload**:
```json
{
  "sub": "tenant-uuid",
  "tenant_id": "tenant-uuid",
  "jti": "token-jti",
  "type": "access",
  "exp": 1234567890
}
```

**Errors**:
- `401`: Invalid email or password

---

### Refresh Token

Get new access token using refresh token.

**Endpoint**: `POST /auth/refresh`

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "tenant": { ... }
}
```

**Errors**:
- `401`: Invalid or expired refresh token

---

### Logout

Revoke current session.

**Endpoint**: `POST /auth/logout`

**Headers**: `Authorization: Bearer <access_token>`

**Response** (200 OK):
```json
{
  "message": "Successfully logged out"
}
```

---

### Logout All Sessions

Revoke all sessions for this tenant.

**Endpoint**: `POST /auth/logout-all`

**Headers**: `Authorization: Bearer <access_token>`

**Response** (200 OK):
```json
{
  "message": "Logged out from 3 sessions"
}
```

---

## Profile

### Get Tenant Profile

Get authenticated tenant's profile.

**Endpoint**: `GET /auth/profile`

**Headers**: `Authorization: Bearer <access_token>`

**Response** (200 OK):
```json
{
  "id": "uuid",
  "name": "Hotel Paradise",
  "email": "admin@hotel.com",
  "hotel_name": "Hotel Paradise",
  "hotel_address": "123 Beach Road, Miami",
  "phone": "+1234567890",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Errors**:
- `401`: Not authenticated

---

### Update Tenant Profile

Update tenant's profile information.

**Endpoint**: `PATCH /auth/profile`

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "name": "Updated Hotel Name",
  "phone": "+9876543210",
  "hotel_address": "456 New Street, LA"
}
```

**Response** (200 OK): Returns updated tenant object.

---

### Change Password

Change tenant's password.

**Endpoint**: `POST /auth/profile/password`

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword456!"
}
```

**Response** (200 OK):
```json
{
  "message": "Password changed successfully"
}
```

**Errors**:
- `400`: Current password is incorrect

---

## Wiki (Knowledge Base)

All wiki endpoints require authentication with `Authorization: Bearer <token>`.

### Ingest Source

Add a new source to the wiki knowledge base.

**Endpoint**: `POST /wiki/ingest`

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "title": "Hotel Amenities Guide",
  "content": "Full content of the document...",
  "source_type": "article",
  "url": "https://example.com/guide",
  "tags": ["amenities", "guide", "hotel"],
  "generate_summary": true,
  "create_entity_pages": true
}
```

**Response** (201 Created):
```json
{
  "source": { ... },
  "created_pages": [ ... ],
  "updated_pages": [ ... ],
  "log_entry_id": "uuid"
}
```

---

### Query Wiki

Ask a question and get LLM-powered answer from wiki content.

**Endpoint**: `POST /wiki/query`

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "question": "What are the check-in times?",
  "max_pages": 5,
  "context": "Guest asking about hotel policies"
}
```

**Response** (200 OK):
```json
{
  "answer": "Check-in time is 3:00 PM...",
  "citations": ["page-1", "page-2"],
  "related_pages": [ ... ]
}
```

---

### Lint Wiki

Run health checks on wiki content.

**Endpoint**: `POST /wiki/lint`

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "check_orphans": true,
  "check_contradictions": true
}
```

**Response** (200 OK):
```json
{
  "issues": [
    {
      "issue_type": "orphan",
      "description": "Page has no incoming links",
      "affected_pages": ["page-uuid"],
      "suggestion": "Add links from related pages"
    }
  ],
  "stats": {
    "total_pages": 50,
    "total_sources": 10,
    "orphan_count": 3
  }
}
```

---

### Get Wiki Index

Get overview of wiki content.

**Endpoint**: `GET /wiki/index`

**Headers**: `Authorization: Bearer <access_token>`

**Response** (200 OK):
```json
{
  "total_pages": 50,
  "total_sources": 10,
  "categories": {
    "entity": 20,
    "concept": 15,
    "source": 10,
    "guide": 5
  },
  "recent_pages": [ ... ],
  "recent_sources": [ ... ]
}
```

---

### List Sources

**Endpoint**: `GET /wiki/sources`

**Query Parameters**:
- `skip` (int, default: 0)
- `limit` (int, default: 50, max: 100)

**Response** (200 OK):
```json
{
  "sources": [ ... ],
  "total": 10
}
```

---

### List Pages

**Endpoint**: `GET /wiki/pages`

**Query Parameters**:
- `skip` (int, default: 0)
- `limit` (int, default: 50, max: 100)

**Response** (200 OK):
```json
{
  "pages": [ ... ],
  "total": 50
}
```

---

### Search Pages

**Endpoint**: `GET /wiki/pages/search?q=<query>&limit=<limit>`

**Response** (200 OK):
```json
{
  "pages": [ ... ],
  "total": 5
}
```

---

## Agent Configuration

All agent endpoints require authentication with `Authorization: Bearer <token>`.

### Get Agent Configuration

Get the current agent configuration for the tenant.

**Endpoint**: `GET /agent/config`

**Headers**: `Authorization: Bearer <access_token>`

**Response** (200 OK):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "system_prompt": "You are a helpful hotel assistant...",
  "personality_prompt": "Be friendly and professional...",
  "is_configured": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

---

### Create Agent Configuration

Create or replace the agent configuration.

**Endpoint**: `POST /agent/config`

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "system_prompt": "You are a helpful hotel assistant...",
  "personality_prompt": "Be friendly and professional..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| system_prompt | string | No | Main system prompt for the AI |
| personality_prompt | string | No | Personality traits and style |

**Response** (201 Created): Returns agent config object.

---

### Update Agent Configuration

Partially update the agent configuration.

**Endpoint**: `PATCH /agent/config`

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "system_prompt": "Updated system prompt..."
}
```

**Response** (200 OK): Returns updated agent config object.

---

### Delete Agent Configuration

Delete the agent configuration.

**Endpoint**: `DELETE /agent/config`

**Headers**: `Authorization: Bearer <access_token>`

**Response** (204 No Content)

---

### Test Agent

Test the agent with a sample question.

**Endpoint**: `POST /agent/test`

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "question": "What are your check-in times?",
  "context": "Guest asking about hotel policies"
}
```

**Response** (200 OK):
```json
{
  "answer": "Check-in time is 3:00 PM...",
  "sources": ["page-1", "page-2"],
  "agent_config_used": true,
  "wiki_context": true,
  "web_search_used": false
}
```

**Behavior**:
- Searches tenant's wiki first
- Falls back to Tavily web search if no wiki results
- Uses agent configuration (system/personality prompts) if configured

---

### Get Agent Status

Get the current configuration status.

**Endpoint**: `GET /agent/status`

**Headers**: `Authorization: Bearer <access_token>`

**Response** (200 OK):
```json
{
  "is_configured": true,
  "has_system_prompt": true,
  "has_personality_prompt": false,
  "config_id": "uuid"
}
```

---

## Health

### Health Check

**Endpoint**: `GET /health`

**Response** (200 OK):
```json
{
  "message": "Inika Backend - Multi-Tenant Hotel Platform",
  "version": "2.0.0",
  "docs": "/docs",
  "multi_tenant": true
}
```

---

## Data Models

### Tenant

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique identifier |
| name | string | Hotel admin's name |
| email | string | Email (unique) |
| hotel_name | string | Hotel name |
| hotel_address | string | Hotel address |
| phone | string | Contact phone |
| is_active | boolean | Account active status |
| created_at | datetime | Account creation time |
| updated_at | datetime | Last update time |

### Token Response

| Field | Type | Description |
|-------|------|-------------|
| access_token | string | JWT access token |
| refresh_token | string | JWT refresh token |
| token_type | string | Always `bearer` |
| tenant | Tenant | Tenant profile |

### WikiSource

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique identifier |
| title | string | Source title |
| source_type | enum | article, paper, document, url |
| file_path | string | Path to source file |
| original_url | string | Original URL if from web |
| summary | string | LLM-generated summary |
| content_hash | string | Hash of content |
| tags | string | JSON array of tags |
| extra_data | string | Additional metadata |
| is_processed | boolean | LLM processing done |
| tenant_id | string | Tenant ID (for isolation) |

### WikiPage

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique identifier |
| title | string | Page title |
| page_type | enum | entity, concept, source, guide |
| slug | string | URL-friendly slug |
| summary | string | Page summary |
| content | string | Page content (markdown) |
| tags | string | JSON array of tags |
| is_draft | boolean | Draft status |
| tenant_id | string | Tenant ID (for isolation) |

### AgentConfig

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique identifier |
| tenant_id | string (UUID) | Tenant ID (unique, FK → tenants.id) |
| system_prompt | string | Main system prompt for AI agent |
| personality_prompt | string | Personality traits and style |
| is_configured | boolean | Whether agent has valid configuration |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Last update timestamp |

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message"
}
```

### Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

---

## Authentication Flow

### Tenant Registration
```
1. Hotel admin sends POST /auth/register
2. Server validates email uniqueness
3. Server creates Tenant record
4. Server creates Session and RefreshToken
5. Server returns tokens + tenant profile
```

### Tenant Login
```
1. Hotel admin sends POST /auth/login with email/password
2. Server validates credentials against Tenant
3. Server creates Session record (with tenant_id)
4. Server returns access_token + refresh_token
5. JWT payload contains tenant_id for multi-tenant isolation
```

### Token Refresh
```
1. Client detects access_token expiring (or preemptively)
2. Client sends POST /auth/refresh with refresh_token
3. Server validates refresh_token (checks tenant_id)
4. Server revokes old refresh_token
5. Server creates new token pair
6. Client receives new tokens
```

### Multi-Tenant Data Isolation
```
1. Every API call includes JWT with tenant_id
2. get_current_tenant dependency extracts tenant from JWT
3. All database queries filter by tenant_id
4. Tenant A cannot access Tenant B's data
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string |
| SECRET_KEY | Yes | JWT signing key (openssl rand -hex 32) |
| ALGORITHM | No | JWT algorithm (default: HS256) |
| ACCESS_TOKEN_EXPIRE_MINUTES | No | Token expiry (default: 30) |
| REFRESH_TOKEN_EXPIRE_DAYS | No | Refresh expiry (default: 7) |
| OPENROUTER_API_KEY | Yes | SHARED - LLM features (all tenants) |
| TAVILY_API_KEY | Yes | SHARED - Web search (all tenants) |
| LLM_MODEL | No | Default: anthropic/claude-3-haiku |
| CORS_ORIGINS | No | Allowed CORS origins |

**Important**: API keys (OPENROUTER_API_KEY, TAVILY_API_KEY) are SHARED across all tenants. Each tenant shares the same OpenRouter and Tavily keys configured in environment variables.

---

## Example Usage

### cURL

```bash
# Register tenant
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Hotel Admin","email":"admin@hotel.com","password":"Pass123!"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@hotel.com","password":"Pass123!"}'

# Get profile (with token)
curl http://localhost:8000/auth/profile \
  -H "Authorization: Bearer <access_token>"

# Ingest wiki source
curl -X POST http://localhost:8000/wiki/ingest \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","content":"Content","source_type":"article"}'

# Create agent configuration
curl -X POST http://localhost:8000/agent/config \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"system_prompt":"You are a hotel concierge.","personality_prompt":"Be friendly."}'

# Get agent status
curl http://localhost:8000/agent/status \
  -H "Authorization: Bearer <access_token>"

# Test agent
curl -X POST http://localhost:8000/agent/test \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"question":"What amenities do you offer?"}'
```

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"

# Register tenant
requests.post(f"{BASE_URL}/auth/register", json={
    "name": "Hotel Admin",
    "email": "admin@hotel.com",
    "password": "Pass123!"
})

# Login
response = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "admin@hotel.com",
    "password": "Pass123!"
})
tokens = response.json()
access_token = tokens["access_token"]

# Get profile
requests.get(f"{BASE_URL}/auth/profile", headers={
    "Authorization": f"Bearer {access_token}"
})

# Ingest wiki source
requests.post(f"{BASE_URL}/wiki/ingest",
    headers={"Authorization": f"Bearer {access_token}"},
    json={"title": "Test", "content": "Content", "source_type": "article"}
)

# Create agent configuration
requests.post(f"{BASE_URL}/agent/config",
    headers={"Authorization": f"Bearer {access_token}"},
    json={"system_prompt": "You are a hotel concierge.", "personality_prompt": "Be friendly."}
)

# Get agent status
requests.get(f"{BASE_URL}/agent/status",
    headers={"Authorization": f"Bearer {access_token}"}
)

# Test agent
requests.post(f"{BASE_URL}/agent/test",
    headers={"Authorization": f"Bearer {access_token}"},
    json={"question": "What amenities do you offer?"}
)
```

### JavaScript (fetch)

```javascript
const BASE_URL = "http://localhost:8000";

// Register tenant
await fetch(`${BASE_URL}/auth/register`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    name: "Hotel Admin",
    email: "admin@hotel.com",
    password: "Pass123!"
  })
});

// Login
const tokens = await fetch(`${BASE_URL}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    email: "admin@hotel.com",
    password: "Pass123!"
  })
}).then(r => r.json());

// Get profile
await fetch(`${BASE_URL}/auth/profile`, {
  headers: { "Authorization": `Bearer ${tokens.access_token}` }
});

// Ingest wiki source
await fetch(`${BASE_URL}/wiki/ingest`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${tokens.access_token}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    title: "Test",
    content: "Content",
    source_type: "article"
  })
});
```

---

## Database Schema

```
tenants (Hotel Admin = Tenant)
├── id (VARCHAR(36), PK)
├── name (VARCHAR)
├── email (VARCHAR, unique)
├── hashed_password (VARCHAR)
├── hotel_name (VARCHAR)
├── hotel_address (VARCHAR)
├── phone (VARCHAR)
├── is_active (BOOLEAN)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)

sessions
├── id (VARCHAR(36), PK)
├── tenant_id (VARCHAR(36), FK → tenants.id)
├── user_id (VARCHAR(36), nullable - for future sub-users)
├── token_jti (VARCHAR, unique)
├── ip_address (VARCHAR)
├── user_agent (VARCHAR)
├── is_active (BOOLEAN)
├── created_at (TIMESTAMP)
├── expires_at (TIMESTAMP)
└── last_activity (TIMESTAMP)

refresh_tokens
├── id (VARCHAR(36), PK)
├── tenant_id (VARCHAR(36), FK → tenants.id)
├── user_id (VARCHAR(36), nullable)
├── token_jti (VARCHAR, unique)
├── is_revoked (BOOLEAN)
├── created_at (TIMESTAMP)
└── expires_at (TIMESTAMP)

wiki_sources (per tenant)
├── id (VARCHAR(36), PK)
├── tenant_id (VARCHAR(36), FK → tenants.id)
├── title (VARCHAR)
├── source_type (ENUM)
├── file_path (VARCHAR)
├── original_url (VARCHAR)
├── summary (TEXT)
├── content_hash (VARCHAR)
├── tags (TEXT - JSON)
├── extra_data (TEXT - JSON)
├── is_processed (BOOLEAN)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)

wiki_pages (per tenant)
├── id (VARCHAR(36), PK)
├── tenant_id (VARCHAR(36), FK → tenants.id)
├── title (VARCHAR)
├── page_type (ENUM)
├── file_path (VARCHAR)
├── slug (VARCHAR)
├── summary (TEXT)
├── content (TEXT)
├── frontmatter (TEXT - JSON)
├── tags (TEXT - JSON)
├── is_draft (BOOLEAN)
├── source_id (VARCHAR(36))
├── created_by_id (VARCHAR(36))
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)

wiki_links (per tenant)
├── id (VARCHAR(36), PK)
├── tenant_id (VARCHAR(36), FK → tenants.id)
├── source_page_id (VARCHAR(36))
├── target_page_id (VARCHAR(36))
├── link_text (VARCHAR)
├── context (TEXT)
└── created_at (TIMESTAMP)

wiki_log (per tenant)
├── id (VARCHAR(36), PK)
├── tenant_id (VARCHAR(36), FK → tenants.id)
├── operation (VARCHAR)
├── description (TEXT)
├── source_id (VARCHAR(36))
├── page_id (VARCHAR(36))
├── user_id (VARCHAR(36))
├── details (TEXT - JSON)
└── created_at (TIMESTAMP)

agent_configs (per tenant, unique per tenant)
├── id (VARCHAR(36), PK)
├── tenant_id (VARCHAR(36), FK → tenants.id, unique)
├── system_prompt (TEXT)
├── personality_prompt (TEXT)
├── is_configured (BOOLEAN)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

---

## Multi-Tenant Notes

### Data Isolation
- All wiki tables have `tenant_id` column
- All database queries filter by `tenant_id`
- Tenant A cannot see or modify Tenant B's data

### Shared Resources
- API keys (OpenRouter, Tavily) are **SHARED** across all tenants
- Environment variables configure the shared keys once
- All tenants use the same LLM and search services

### JWT Structure
```json
{
  "sub": "tenant-uuid",
  "tenant_id": "tenant-uuid",
  "jti": "unique-token-id",
  "type": "access|refresh",
  "exp": 1234567890
}
```