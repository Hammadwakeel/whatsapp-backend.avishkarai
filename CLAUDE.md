# Inika Backend - Multi-Tenant Hotel Platform

## Stack
- **Framework**: FastAPI (async)
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Auth**: JWT with access/refresh tokens (tenant-based)
- **LLM**: OpenRouter (Claude) integration
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
│   ├── api/           # Route handlers (auth, wiki)
│   ├── core/          # Config, security, database
│   ├── models/        # SQLAlchemy models (tenant, wiki)
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic (tenant, wiki, LLM)
│   └── main.py       # FastAPI app entry
├── alembic/          # Database migrations
├── docs/             # Documentation
│   ├── API.md        # Auth API reference
│   ├── INTEGRATION.md # Frontend integration
│   └── WIKI.md       # Wiki system docs
├── wiki/             # Wiki markdown files
├── tests/            # Unit & integration tests
├── skills.md         # Claude Code skills
├── .env.example
├── docker-compose.yml
└── requirements.txt
```

## Documentation
- **Auth API**: `docs/API.md`
- **Frontend Integration**: `docs/INTEGRATION.md`
- **Wiki API**: `docs/WIKI.md`
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
```

## Key Dependencies
- fastapi, uvicorn - Web framework
- sqlalchemy[asyncio], asyncpg - Async DB
- python-jose - JWT tokens
- passlib[bcrypt] - Password hashing
- httpx - HTTP client (for OpenRouter/Tavily)
- pydantic, pydantic-settings - Validation

## GitHub Repository
- **Remote**: https://github.com/Hammadwakeel/whatsapp-backend.avishkarai.git
- **Branch**: main