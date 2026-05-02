# Inika Backend - Multi-Tenant Hotel Platform

## Stack
- **Framework**: FastAPI (async)
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Auth**: JWT with access/refresh tokens (tenant-based)
- **LLM**: OpenRouter (Claude) integration
- **WhatsApp**: Evolution API (free, open-source)
- **Migration**: Alembic
- **Testing**: pytest + pytest-asyncio

## Multi-Tenant Architecture
- Each hotel (tenant) has isolated data with `tenant_id` on all tables
- Hotel admin = tenant (no separate user accounts for admin)
- Shared API keys across all tenants (OpenRouter, Tavily, etc.)
- JWT tokens include `tenant_id` for tenant identification

## Project Structure
```
inika-backend/
├── app/
│   ├── api/           # Route handlers (auth, wiki, whatsapp, journey)
│   ├── core/          # Config, security, database
│   ├── models/        # SQLAlchemy models (tenant, wiki, journey)
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic (tenant, wiki, LLM, evolution, booking, journey)
│   └── main.py       # FastAPI app entry
├── alembic/          # Database migrations
├── docs/             # Documentation
│   ├── API.md        # Auth API reference
│   ├── INTEGRATION.md # Frontend integration
│   ├── WIKI.md       # Wiki system docs
│   ├── WHATSAPP.md   # WhatsApp/Evolution API docs
│   ├── BOOKING.md    # Booking system docs
│   ├── WEBHOOK.md    # Webhook integration docs
│   └── JOURNEY.md    # Journey module docs
├── wiki/             # Wiki markdown files
├── tests/            # Unit & integration tests
├── docker-compose.evolution.yml  # Evolution API setup
├── skills.md         # Claude Code skills
├── .env.example
├── docker-compose.yml
└── requirements.txt
```

## Documentation
- **Auth API**: `docs/API.md`
- **Frontend Integration**: `docs/INTEGRATION.md`
- **Wiki API**: `docs/WIKI.md`
- **WhatsApp Integration**: `docs/WHATSAPP.md`
- **Webhook Integration**: `docs/WEBHOOK.md`
- **Booking Integration**: `docs/BOOKING.md`
- **Journey Module**: `docs/JOURNEY.md`
- **Claude Skills**: `skills.md`
- **Swagger UI**: `http://localhost:8000/docs`

## Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string |
| SECRET_KEY | Yes | JWT signing key (openssl rand -hex 32) |
| OPENROUTER_API_KEY | Yes | Shared for all tenants - LLM features |
| TAVILY_API_KEY | Yes | Shared for all tenants - Web search |
| LLM_MODEL | No | Default: anthropic/claude-3-haiku |
| ACCESS_TOKEN_EXPIRE_MINUTES | No | Token expiry (default: 30) |
| REFRESH_TOKEN_EXPIRE_DAYS | No | Refresh expiry (default: 7) |
| EVOLUTION_URL | No | Evolution API URL (default: http://localhost:8080) |
| EVOLUTION_API_KEY | No | Evolution API authentication key |
| EVOLUTION_INSTANCE_NAME | No | Instance name for WhatsApp (default: inika) |
| INIKA_API_KEY | No | External booking system API key |
| INIKA_BOOKING_KEY | No | External booking system access key |
| OPENWEATHER_API_KEY | No | OpenWeatherMap API key for weather data |

## Core Features

### Authentication (Tenant-Based)
- Register, login, logout, token refresh
- JWT access + refresh tokens with tenant_id
- Session tracking and revocation per tenant
- Password hashing with bcrypt

### Multi-Tenant Isolation
- All tables have `tenant_id` for data isolation
- Tenant A cannot access Tenant B's data
- Shared API keys (OpenRouter, Tavily) across all tenants

### Wiki System (LLM-Powered)
- **Ingest**: Add sources, auto-generate summaries and entity pages
- **Query**: LLM-powered answers from wiki content
- **Lint**: Health checks for contradictions/orphans
- **Search**: Full-text search across pages
- **Cross-references**: `[[Wiki Links]]` between pages

### WhatsApp Integration (Evolution API)
- Free, open-source WhatsApp gateway
- QR code generation via API
- Webhook support for incoming messages
- Message history and session management

### Booking System (External API Integration)
- Sync guest inventory from external booking system
- Guest lookup by ID, phone, or room number
- Journey tracking with milestones
- Booking statistics and today's operations

### Journey Module (Guest Engagement & Smart Messaging)
- AI-powered contextual messaging to hotel guests
- Time-based messages (morning, breakfast, lunch, dinner, evening)
- Weather-based adaptations (sunny, rainy, cold recommendations)
- Guest status messages (Due In, Welcome, Checkout, Feedback)
- AI conversation support with RAG from wiki content
- Rate limiting (max messages per guest per day)
- Full message logging for compliance

### Journey Database Tables
- `journey_config` - Per-tenant journey configuration
- `journey_schedule` - Scheduled message templates
- `journey_message_log` - All sent/received messages
- `journey_conversation` - Guest conversation threads
- `journey_message` - Individual messages in conversations

## Database Tables

### Auth Tables
- `tenants` - Hotel admin accounts (tenant = hotel admin)
- `sessions` - Active JWT sessions per tenant
- `refresh_tokens` - Token management per tenant

### Wiki Tables
- `wiki_sources` - Raw sources (per tenant)
- `wiki_pages` - Generated pages (per tenant)
- `wiki_links` - Cross-references (per tenant)
- `wiki_log` - Operation history (per tenant)

### WhatsApp Tables
- `whatsapp_sessions` - WhatsApp connection status per tenant
- `whatsapp_messages` - Message history (inbound/outbound)

## Running
```bash
# Install
pip install -r requirements.txt

# Development
source venv/bin/activate && uvicorn app.main:app --reload

# Production
uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000

# Docker
docker-compose up

# Migrations
alembic upgrade head

# Start Evolution API (WhatsApp gateway)
docker-compose up -d
```

## Key Dependencies
- fastapi, uvicorn - Web framework
- sqlalchemy[asyncio], asyncpg - Async DB
- python-jose - JWT tokens
- passlib[bcrypt] - Password hashing
- httpx - HTTP client (for OpenRouter/Tavily/Evolution)
- pydantic, pydantic-settings - Validation
- qrcode[pil] - QR code generation

## GitHub Repository
- **Remote**: https://github.com/Hammadwakeel/whatsapp-backend.avishkarai.git
- **Branch**: main