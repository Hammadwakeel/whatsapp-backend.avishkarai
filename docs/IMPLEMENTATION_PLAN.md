# Multi-Tenant Hotel SaaS Platform - Implementation Plan

## Overview

A multi-tenant platform for hotels where each hotel admin can:
1. Authenticate and manage their profile
2. Connect their WhatsApp Business account via OpenClaw
3. Upload knowledge base files and configure AI agent
4. Let AI agent answer WhatsApp user queries using RAG + Web Search

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GCP VM                                      │
│                                                                     │
│  ┌─────────────┐     ┌─────────────────────┐     ┌─────────────┐ │
│  │   OpenClaw  │────▶│   Inika Backend     │◀────│  WhatsApp   │ │
│  │   Gateway   │     │   (FastAPI)         │     │  Users      │ │
│  │             │     │                     │     │             │ │
│  │ - Session 1 │     │  - Multi-tenant Auth │     │             │ │
│  │   (Hotel A) │     │  - Wiki (RAG)       │     │             │ │
│  │ - Session 2 │     │  - Agent Config     │     │             │ │
│  │   (Hotel B) │     │  - Message Storage  │     │             │ │
│  │ - Session N │     │  - API Key Mgmt    │     │             │ │
│  └─────────────┘     └─────────────────────┘     └─────────────┘ │
│         │                     │                                      │
│         │            ┌────────┴────────┐                           │
│         │            │   PostgreSQL     │                           │
│         │            │   (Multi-tenant) │                           │
│         │            └─────────────────┘                           │
└─────────┴────────────────────────────┴───────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │     Tavily API       │
                    │  (Web Search)        │
                    └─────────────────────┘
```

---

## System Flow

### Admin Flow
```
Admin Signup/Login
       ↓
Profile Page (manage account)
       ↓
WhatsApp Page (scan QR, connect)
       ↓
Knowledge Base Page
  ├── Upload PDF/TXT → Ingest to Wiki
  ├── Set System Prompt
  ├── Set Personality Prompt
  └── Configure API Keys (OpenRouter, Tavily)
       ↓
Test Agent (preview responses)
```

### User Message Flow
```
WhatsApp User sends message
       ↓
OpenClaw (tenant session) → Forwards to Inika API
       ↓
Inika: Identify tenant by session
       ↓
Check if agent configured?
  → No: Return "Agent not configured" or basic greeting
  → Yes: Continue
       ↓
Query Tenant's Wiki (RAG)
       ↓
Answer quality check (relevance threshold)
       ↓
Found? ──Yes──▶ Generate response
       │
       No
       ↓
Tavily Web Search
       ↓
Generate response with sources
       ↓
Store message in DB (tenant isolated)
       ↓
Return response to OpenClaw
       ↓
OpenClaw → WhatsApp User
```

---

## Database Schema

### Multi-Tenant Foundation

All tables include `tenant_id` for data isolation.

```sql
-- Tenants table
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add tenant_id to existing tables
ALTER TABLE users ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE user_history ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE sessions ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE refresh_tokens ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE wiki_sources ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE wiki_pages ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE wiki_links ADD COLUMN tenant_id UUID REFERENCES tenants(id);
ALTER TABLE wiki_log ADD COLUMN tenant_id UUID REFERENCES tenants(id);
```

### Agent Configuration
```sql
CREATE TABLE agent_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID UNIQUE REFERENCES tenants(id),
    system_prompt TEXT,
    personality_prompt TEXT,
    is_configured BOOLEAN DEFAULT FALSE,
    openai_api_key TEXT,  -- Optional override per tenant
    tavily_api_key TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### WhatsApp Sessions
```sql
CREATE TABLE whatsapp_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID UNIQUE REFERENCES tenants(id),
    openclaw_session_id VARCHAR(255),
    phone_number VARCHAR(50),
    status VARCHAR(50),  -- active, disconnected, error
    qr_code TEXT,  -- Base64 encoded QR
    connected_at TIMESTAMP,
    last_activity TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Message Storage
```sql
CREATE TABLE whatsapp_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    session_id UUID REFERENCES whatsapp_sessions(id),
    direction VARCHAR(10),  -- inbound, outbound
    from_number VARCHAR(50),
    to_number VARCHAR(50),
    content TEXT,
    agent_response TEXT,
    wiki_sources JSONB,
    web_search_results JSONB,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_messages_tenant ON whatsapp_messages(tenant_id);
CREATE INDEX idx_messages_session ON whatsapp_messages(session_id);
CREATE INDEX idx_messages_created ON whatsapp_messages(created_at);
```

### Per-Tenant API Keys
```sql
CREATE TABLE tenant_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    provider VARCHAR(100) NOT NULL,  -- openrouter, tavily, etc.
    key_value TEXT NOT NULL,
    config JSONB,  -- Additional config per provider
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_tenant_provider ON tenant_api_keys(tenant_id, provider);
```

---

## API Endpoints

### Auth (Tenant-aware)
```
POST /auth/register          # Create tenant account
POST /auth/login             # Login, get JWT with tenant_id
POST /auth/refresh           # Refresh tokens
POST /auth/logout            # Revoke session
```

### Profile
```
GET  /profile                # Get current tenant profile
PUT  /profile                # Update profile
POST /profile/password       # Change password
```

### WhatsApp
```
GET  /whatsapp/status        # Get connection status
POST /whatsapp/connect       # Generate QR code
POST /whatsapp/disconnect    # Disconnect WhatsApp
GET  /whatsapp/qr            # Get current QR code
```

### Agent Configuration
```
GET  /agent/config           # Get agent configuration
PUT  /agent/config           # Update agent (prompts, API keys)
POST /agent/test            # Test agent with sample query
GET  /agent/messages         # Get conversation history
```

### Knowledge Base
```
POST /knowledge/upload       # Upload PDF/TXT file
GET  /knowledge/files        # List uploaded files
DELETE /knowledge/files/{id} # Delete file
POST /knowledge/ingest       # Trigger manual re-ingest
GET  /knowledge/stats        # Wiki stats (pages, sources)
```

### Webhook (OpenClaw → Inika)
```
POST /webhook/whatsapp       # Receive messages from OpenClaw
POST /webhook/events         # OpenClaw events (connect, disconnect)
```

---

## Implementation Phases

### Phase 1: Multi-Tenant Foundation

**Duration**: 1-2 days

**Tasks**:
1. Create `tenants` table
2. Add `tenant_id` to all existing tables
3. Create tenant middleware (extract from JWT)
4. Update auth flow to work with tenants
5. Create tenant isolation service

**Files to Create/Modify**:
- `app/models/tenant.py` - New tenant model
- `app/core/middleware.py` - Tenant middleware
- `app/services/tenant_service.py` - Tenant isolation logic
- `app/api/auth.py` - Update for multi-tenant

---

### Phase 2: Shared API Keys

**Duration**: 0.5 day

**Tasks**:
1. Configure shared API keys in environment (OPENROUTER_API_KEY, TAVILY_API_KEY)
2. Update LLMService to use shared OpenRouter key
3. Create TavilySearchService for web search fallback
4. Document that keys are shared across all tenants

**Files to Create/Modify**:
- `app/core/config.py` - Add TAVILY_API_KEY setting
- `app/services/search_service.py` - NEW: Tavily search service
- `app/services/llm_service.py` - Update for shared key

**Key Decision**: API keys (OpenRouter, Tavily) are SHARED across all tenants, not per-tenant. Each tenant shares the same LLM and search services configured in environment variables.

---

### Phase 3: Agent Configuration ✅

**Duration**: 1 day

**Tasks**:
1. ✅ Create `agent_configs` table
2. ✅ Create agent config service
3. ✅ Create agent configuration endpoints
4. ✅ Update documentation

**Files Created/Modified**:
- `app/models/agent.py` - Agent config model
- `app/services/agent_service.py` - Agent logic
- `app/api/agent.py` - Agent routes
- `app/schemas/agent.py` - Pydantic schemas
- `app/main.py` - Registered agent router
- `docs/API.md` - Added agent documentation
- `tests/test_agent.py` - Agent tests

**Status**: Complete (32 tests passing)

---

### Phase 4: WhatsApp Session Management

**Duration**: 1-2 days

**Tasks**:
1. Create `whatsapp_sessions` table
2. Create OpenClaw client service
3. QR code generation/management
4. Session status endpoints

**Files to Create/Modify**:
- `app/models/whatsapp.py` - WhatsApp session model
- `app/services/openclaw_client.py` - OpenClaw API client
- `app/api/whatsapp.py` - WhatsApp routes

---

### Phase 5: Message Storage

**Duration**: 0.5 day

**Tasks**:
1. Create `whatsapp_messages` table
2. Message storage service
3. Message history endpoints

**Files to Create/Modify**:
- Update `app/models/whatsapp.py` with messages
- `app/services/message_service.py` - Message storage
- Update `app/api/whatsapp.py`

---

### Phase 6: File Upload & Knowledge Base

**Duration**: 1-2 days

**Tasks**:
1. File upload endpoint (PDF, TXT)
2. File storage (local or GCS)
3. Ingest service (parse → wiki)
4. Knowledge base UI endpoints

**Files to Create/Modify**:
- `app/api/knowledge.py` - Upload and management routes
- `app/services/ingest_service.py` - File parsing and ingest
- `app/services/file_service.py` - File storage

---

### Phase 7: OpenClaw Integration

**Duration**: 2-3 days

**Tasks**:
1. Install OpenClaw on VM
2. Create webhook endpoints
3. Tool definitions for Inika API
4. Session management integration

**Files to Create/Modify**:
- `app/api/webhook.py` - OpenClaw webhooks
- `app/services/openclaw_tools.py` - Tool definitions
- OpenClaw config file

**External**:
- OpenClaw daemon setup
- WhatsApp session pairing

---

### Phase 8: Agent & RAG Logic

**Duration**: 2-3 days

**Tasks**:
1. Query flow: Wiki → Tavily fallback
2. Response generation
3. Message routing back to OpenClaw
4. Agent test endpoint

**Files to Create/Modify**:
- `app/services/rag_service.py` - RAG logic
- `app/services/response_service.py` - Generate responses
- Update `app/services/wiki_service.py`
- Update `app/api/webhook.py`

---

### Phase 9: Admin UI Pages

**Duration**: 3-5 days

**Tasks**:
1. Profile page
2. WhatsApp page (QR display, status, connect/disconnect)
3. Knowledge Base page (upload, prompts, test)
4. Test agent functionality

**Frontend** (if using React):
- `pages/Profile.tsx`
- `pages/WhatsApp.tsx`
- `pages/KnowledgeBase.tsx`

---

### Phase 10: Testing & Deployment

**Duration**: 2-3 days

**Tasks**:
1. Unit tests for all services
2. Integration tests
3. Load testing
4. GCP deployment
5. Monitoring setup

---

## File Structure (Final)

```
inika-backend/
├── app/
│   ├── api/
│   │   ├── auth.py          # Auth routes
│   │   ├── profile.py       # Profile routes
│   │   ├── whatsapp.py      # WhatsApp routes
│   │   ├── agent.py          # Agent config routes
│   │   ├── knowledge.py      # Knowledge base routes
│   │   ├── webhook.py       # OpenClaw webhooks
│   │   └── keys.py          # API key management
│   ├── core/
│   │   ├── config.py        # Settings
│   │   ├── database.py      # DB connection
│   │   ├── security.py      # JWT, password
│   │   └── middleware.py     # Tenant middleware
│   ├── models/
│   │   ├── tenant.py        # Tenant model
│   │   ├── user.py          # User model
│   │   ├── agent.py          # Agent config
│   │   ├── whatsapp.py       # WhatsApp sessions + messages
│   │   ├── wiki.py          # Wiki models
│   │   └── api_keys.py      # API keys
│   ├── schemas/
│   │   └── ...              # Pydantic schemas
│   ├── services/
│   │   ├── tenant_service.py
│   │   ├── auth_service.py
│   │   ├── agent_service.py
│   │   ├── openclaw_client.py
│   │   ├── openclaw_tools.py
│   │   ├── rag_service.py
│   │   ├── response_service.py
│   │   ├── ingest_service.py
│   │   ├── file_service.py
│   │   └── message_service.py
│   └── main.py
├── docs/
│   ├── IMPLEMENTATION_PLAN.md  # This file
│   └── ...
├── wiki/                    # Tenant wiki files
│   └── {tenant_id}/
│       ├── sources/
│       └── pages/
└── uploads/                 # Tenant uploaded files
    └── {tenant_id}/
```

---

## Configuration

### Environment Variables
```bash
# Existing
DATABASE_URL=postgresql+asyncpg://...
SECRET_KEY=...

# New
TAVILY_API_KEY=tvly-dev-...  # Default for tenants without own key
OPENCLAW_URL=http://127.0.0.1:18789
OPENCLAW_API_KEY=...
UPLOAD_DIR=./uploads
```

### OpenClaw Config
```json
{
  "gateway": {
    "port": 18789,
    "tools": ["inika-agent"],
    "channels": ["whatsapp"]
  },
  "tools": {
    "inika-agent": {
      "url": "http://localhost:8000",
      "auth": "bearer"
    }
  }
}
```

---

## OpenClaw Tool Definition

```json
{
  "name": "inika-agent",
  "description": "AI agent for hotel knowledge base",
  "actions": [
    {
      "name": "query",
      "description": "Query the hotel's knowledge base",
      "params": {
        "tenant_id": "string",
        "query": "string",
        "session_id": "string"
      }
    },
    {
      "name": "get_status",
      "description": "Get agent configuration status",
      "params": {
        "tenant_id": "string"
      }
    }
  ]
}
```

---

## Acceptance Criteria

### Phase 1 (Multi-Tenant) ✅
- [x] Tenant can register and login
- [x] All data is tenant-isolated
- [x] JWT contains tenant_id

### Phase 2 (Shared API Keys) ✅
- [x] OpenRouter API key is shared across all tenants
- [x] Tavily API key is shared across all tenants
- [x] LLM service uses shared keys

### Phase 3 (Agent Configuration) ✅
- [x] Admin can set system/personality prompts
- [x] Agent configuration is tenant-isolated
- [x] Agent test endpoint works
- [x] Agent status endpoint works

### Phase 4-5 (WhatsApp)
- [ ] QR code displayed for WhatsApp connect
- [ ] Session status tracked
- [ ] Messages stored per tenant

### Phase 6-7 (Knowledge + OpenClaw)
- [ ] File upload works (PDF, TXT)
- [ ] Files ingested to wiki
- [ ] OpenClaw webhook receives messages

### Phase 8-9 (Agent + RAG)
- [ ] Query searches tenant wiki first
- [ ] Falls back to Tavily if no result
- [ ] Response sent back via OpenClaw
- [ ] Admin UI pages functional

### Phase 10 (Deployment)
- [ ] Deployed on GCP VM
- [ ] Multi-tenant isolation verified
- [ ] End-to-end flow tested

---

## Timeline Estimate

| Phase | Duration | Total |
|-------|----------|-------|
| Phase 1: Multi-Tenant Foundation | 1-2 days | 2 days |
| Phase 2: Per-Tenant API Keys | 0.5 day | 2.5 days |
| Phase 3: Agent Configuration | 1 day | 3.5 days |
| Phase 4: WhatsApp Sessions | 1-2 days | 5 days |
| Phase 5: Message Storage | 0.5 day | 5.5 days |
| Phase 6: Knowledge Base | 1-2 days | 7 days |
| Phase 7: OpenClaw Integration | 2-3 days | 10 days |
| Phase 8: Agent & RAG | 2-3 days | 13 days |
| Phase 9: Admin UI | 3-5 days | 18 days |
| Phase 10: Testing & Deploy | 2-3 days | 21 days |

**Total Estimate: ~3 weeks**

---

## Open Questions

1. **Frontend framework** - React, Vue, or separate?
2. **File storage** - Local disk or GCS?
3. **Authentication for OpenClaw** - Same JWT or separate?
4. **Rate limiting** - Per tenant or global?
5. **Monitoring** - What metrics to track?

---

*Last Updated: 2026-05-01*
*Author: Claude Code*