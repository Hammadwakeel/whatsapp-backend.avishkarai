# Inika Backend - Multi-Tenant Hotel Platform

Multi-tenant SaaS platform for hotels with WhatsApp AI agent integration and intelligent guest messaging.

## Features

- **Multi-Tenant Architecture**: Each hotel (tenant) has isolated data
- **JWT Authentication**: Tenant-based auth with access/refresh tokens
- **Wiki Knowledge Base**: LLM-powered RAG for hotel AI agent
- **WhatsApp Integration**: Evolution API gateway for WhatsApp sessions
- **Journey Module**: AI-powered guest messaging (weather, time, status-based)
- **Agent Configuration**: Custom AI agent personality and system prompts
- **Booking Integration**: External booking system sync
- **Shared API Keys**: OpenRouter, Tavily, OpenWeatherMap shared across all tenants

## Tech Stack

### Backend
- **Framework**: FastAPI (async)
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Auth**: JWT with tenant_id isolation
- **LLM**: OpenRouter (Claude) integration
- **WhatsApp**: Evolution API (free, open-source)
- **Weather**: OpenWeatherMap API
- **Testing**: pytest + pytest-asyncio

### Frontend
- **Framework**: Next.js 14+ (App Router)
- **Styling**: Tailwind CSS
- **Animations**: Framer Motion
- **State**: React Context + Hooks

## Project Structure

```
inika-backend/
├── app/                    # Backend (FastAPI)
│   ├── api/               # Route handlers
│   ├── core/              # Config, database, security
│   ├── models/            # SQLAlchemy models
│   ├── services/          # Business logic
│   └── main.py            # App entry point
├── frontend/              # Frontend (Next.js)
│   ├── app/               # Pages (App Router)
│   ├── components/        # Shared components
│   └── lib/               # API client
├── docs/                  # Documentation
├── alembic/               # Database migrations
├── wiki/                  # Wiki markdown files
└── tests/                 # Test suites
```

## Quick Start

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start database
docker-compose up -d

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string |
| SECRET_KEY | Yes | JWT signing key |
| OPENROUTER_API_KEY | Yes | SHARED - LLM features |
| TAVILY_API_KEY | Yes | SHARED - Web search |
| EVOLUTION_URL | No | WhatsApp gateway URL |
| EVOLUTION_API_KEY | No | Evolution API authentication |
| INIKA_API_KEY | No | External booking API key |
| OPENWEATHER_API_KEY | No | Weather data API |

## API Documentation

| Endpoint | Description |
|----------|-------------|
| `docs/API.md` | Auth, Profile, Agent APIs |
| `docs/INTEGRATION.md` | Frontend integration guide |
| `docs/WIKI.md` | Wiki knowledge base system |
| `docs/WHATSAPP.md` | WhatsApp integration guide |
| `docs/BOOKING.md` | Booking system integration |
| `docs/JOURNEY.md` | Journey module documentation |
| `docs/WEBHOOK.md` | Webhook endpoints |

**Swagger UI**: `http://localhost:8000/docs`

## Modules

### Authentication
- Tenant registration and login
- JWT access + refresh tokens
- Session management (logout, logout-all)
- Profile management

### Wiki / Knowledge Base
- Source ingestion with auto-summarization
- Entity page generation
- Cross-references between pages
- LLM-powered query answers

### Agent Configuration
- System prompt customization
- Personality prompt settings
- RAG-enabled responses

### WhatsApp Integration
- QR code connection
- Message sending/receiving
- Webhook support for incoming messages
- Session management

### Journey Module (Guest Messaging)
- AI-powered contextual messages
- Time-based (morning, breakfast, lunch, dinner, evening)
- Weather-based adaptations
- Guest status messages (Due In, Welcome, Checkout)
- RAG-enabled AI conversations

### Booking Integration
- Guest inventory sync
- Booking statistics
- Guest journey tracking

## Testing

```bash
# Backend tests
pytest tests/test_tenant_flow.py -v
pytest tests/test_whatsapp.py -v
pytest tests/test_booking.py -v
pytest tests/test_journey.py -v

# All tests
pytest tests/ -v
```

## GitHub

Repository: https://github.com/Hammadwakeel/whatsapp-backend.avishkarai.git