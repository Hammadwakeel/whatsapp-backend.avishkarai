# Claude Code Skills for Inika Backend

This file documents my knowledge, patterns, and behaviors for working with this project.

---

## Project Overview

- **Project**: Inika Backend - Multi-Tenant Hotel Platform with WhatsApp AI Agent
- **Stack**: FastAPI, PostgreSQL, JWT Auth, Wiki with LLM, OpenClaw Integration
- **Location**: `/home/hammad/Downloads/work/Job/inika-backend`
- **GitHub**: https://github.com/Hammadwakeel/whatsapp-backend.avishkarai.git

---

## Multi-Tenant Architecture

### Key Principles
1. **Tenant = Hotel Admin**: Each hotel is a tenant, and the hotel admin IS the tenant
2. **Shared API Keys**: OpenRouter, Tavily, etc. are SHARED across all tenants (not per-tenant)
3. **Data Isolation**: All tables have `tenant_id` for multi-tenant isolation
4. **JWT contains tenant_id**: Access tokens include `tenant_id` for tenant identification

### Tenant Flow
- Hotel admin registers → Creates a Tenant
- Hotel admin logs in → Gets JWT with tenant_id
- All API calls use tenant_id from JWT
- Hotel A cannot access Hotel B's data

---

## Code Patterns

### Import Organization
```python
# Core imports first
from typing import Optional, List

# Third-party
from fastapi import Depends, HTTPException

# Local imports
from app.core import get_db, get_settings
from app.models import Tenant
from app.services import TenantService
from app.api.deps import get_current_tenant
```

### Service Pattern
```python
class MyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Initialize other dependencies

    async def my_method(self, param: str) -> MyModel:
        # Business logic here
        pass
```

### Schema Validation
- Use `field_validator` with `mode='before'` for JSON string parsing
- Always handle `Optional` types properly
- Use `model_validate()` for ORM-to-Pydantic conversion

### API Routes (Tenant-Based)
```python
@router.post("/endpoint", response_model=ResponseModel)
async def handler(
    request: Request,
    body: RequestBody,
    current_tenant: Tenant = Depends(get_current_tenant),  # Changed from get_current_user
    db: AsyncSession = Depends(get_db),
):
    # Implementation - tenant_id from current_tenant.id
    pass
```

---

## Common Fixes

### bcrypt + passlib version conflict
- Use `bcrypt==4.0.1` (not 5.x) with passlib
- Add to requirements.txt: `bcrypt==4.0.1`

### SQLAlchemy "metadata" reserved name
- Don't use `metadata` as column name
- Use `extra_data` or `meta` instead

### Type imports from typing
- Use `List`, `Dict`, etc. (capitalized)
- Don't use lowercase `list`, `dict` in imports

### JSON tags in Pydantic
- Store JSON arrays as strings in DB
- Use `field_validator` to parse on read

---

## Testing Workflow

1. Start server: `source venv/bin/activate && uvicorn app.main:app --reload`
2. Register tenant: `curl -X POST localhost:8000/auth/register -d '{"name":"Hotel","email":"...","password":"..."}'`
3. Login: `curl -X POST localhost:8000/auth/login -d '{"email":"...","password":"..."}'`
4. Test endpoint: `curl -H "Authorization: Bearer <token>" ...`

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection |
| SECRET_KEY | Yes | JWT signing key |
| OPENROUTER_API_KEY | Yes | SHARED across all tenants - LLM features |
| TAVILY_API_KEY | Yes | SHARED across all tenants - Web search |
| LLM_MODEL | No | Default: anthropic/claude-3-haiku |
| WIKI_PATH | No | Default: wiki |
| EVOLUTION_URL | No | Evolution API URL (WhatsApp gateway) |
| EVOLUTION_API_KEY | No | Evolution API authentication |
| INIKA_API_KEY | No | External booking API key |
| INIKA_BOOKING_KEY | No | External booking access key |
| OPENWEATHER_API_KEY | No | OpenWeatherMap API key for weather |

**Important**: API keys (OpenRouter, Tavily) are SHARED, not per-tenant. All tenants use the same keys configured in environment variables.

---

## Database Models

### Tenant Model (app/models/tenant.py)
- `Tenant` - Hotel admin accounts (tenant = hotel admin)

### User Models (app/models/user.py)
- `User` - User accounts (for future sub-user per tenant)
- `UserHistory` - Change audit log
- `Session` - JWT sessions (tenant_id FK)
- `RefreshToken` - Token management (tenant_id FK)

### Wiki Models (app/models/wiki.py)
- `WikiSource` - Raw sources (per tenant via tenant_id)
- `WikiPage` - Generated pages (per tenant via tenant_id)
- `WikiLink` - Cross-references between pages (per tenant via tenant_id)
- `WikiLog` - Operation history (per tenant via tenant_id)

### Booking Models (app/services/booking_service.py)
- `GuestInventory` - Guest data synced from external booking API (per tenant)

### Journey Models (app/models/journey.py)
- `JourneyConfig` - Journey module configuration per tenant
- `JourneySchedule` - Scheduled message templates
- `JourneyMessageLog` - All sent/received messages
- `JourneyConversation` - Guest conversation threads
- `JourneyMessage` - Individual messages in conversations

---

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `app/api/` | Route handlers (auth, wiki, whatsapp, booking, journey) |
| `app/core/` | Config, database, security |
| `app/models/` | SQLAlchemy models (tenant, user, wiki, journey) |
| `app/services/` | Business logic (tenant, wiki, LLM, evolution, booking, journey) |
| `app/api/booking.py` | Booking/external API integration |
| `app/api/journey.py` | Journey/guest messaging endpoints |
| `app/services/journey/` | Journey module services (weather, messaging, scheduling) |
| `app/services/inika_client.py` | External Inika API client |
| `app/services/booking_service.py` | Guest management service |

## Documentation

| File | Purpose |
|------|---------|
| `docs/API.md` | Auth, Wiki, Agent, WhatsApp, Booking endpoints |
| `docs/INTEGRATION.md` | Frontend integration examples |
| `docs/WIKI.md` | Wiki system documentation |
| `docs/WHATSAPP.md` | WhatsApp frontend integration |
| `docs/WEBHOOK.md` | Webhook endpoints for external systems |
| `docs/BOOKING.md` | Booking system integration guide |
| `docs/JOURNEY.md` | Journey module documentation |
| `wiki/` | Markdown wiki files |
| `docs/` | Documentation |

---

## Workflows

### Adding a New API Feature
1. Create model in `app/models/` with `tenant_id` column
2. Create schema in `app/schemas/`
3. Create service in `app/services/`
4. Create route in `app/api/` using `get_current_tenant`
5. Add to main.py router
6. Update __init__.py exports

### Database Changes
1. Update model in `app/models/`
2. Create migration: `alembic revision --autogenerate -m "description"`
3. Review migration in `alembic/versions/`
4. Apply: `alembic upgrade head`

### Wiki Ingestion Flow
1. Source saved to `wiki/sources/`
2. LLM generates summary (using shared OpenRouter key)
3. Entity pages auto-created
4. Cross-links established
5. Log entry created

---

## GitHub Workflow

When user says "push the code", execute:
```bash
cd /home/hammad/Downloads/work/Job/inika-backend
git add .
git commit -m "Your commit message"
git push origin main
```

Repository: https://github.com/Hammadwakeel/whatsapp-backend.avishkarai.git

---

## Notes

- Always authenticate wiki endpoints with JWT using `get_current_tenant`
- OpenRouter & Tavily API keys are SHARED across all tenants
- Keys stored in `.env` (never commit secrets)
- Wiki files can be synced with Obsidian
- Use `slugify()` for URL-safe page titles
- LLM service falls back gracefully on errors

---

## Phase Roadmap

1. **Phase 1: Multi-Tenant Foundation** ✓ (Complete)
   - Tenant model, JWT auth, multi-tenant isolation

2. **Phase 2: Shared API Keys** ✓ (Complete)
   - OpenRouter, Tavily keys from env (shared, not per-tenant)

3. **Phase 3: Agent Configuration** ✓ (Complete)
   - AgentConfig model for system/personality prompts

4. **Phase 4: WhatsApp Integration** ✓ (Complete)
   - Evolution API integration for WhatsApp gateway

5. **Phase 5: Journey Module** ✓ (Complete)
   - AI-powered guest messaging (weather, time, status)
   - RAG-enabled AI conversation support
   - Message scheduling and broadcasting

---

## CLI Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Start development server
source venv/bin/activate && uvicorn app.main:app --reload

# Run with Docker
docker-compose up

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
alembic downgrade -1

# Run tests
pytest tests/test_tenant_flow.py

# Generate secret key
openssl rand -hex 32

# Push to GitHub
git add .
git commit -m "message"
git push origin main
```