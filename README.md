# Inika Backend - Multi-Tenant Hotel Platform

Multi-tenant SaaS platform for hotels with WhatsApp AI agent integration and intelligent guest messaging.

## Features

- **Multi-Tenant Architecture**: Each hotel (tenant) has isolated data
- **JWT Authentication**: Tenant-based auth with access/refresh tokens
- **Wiki Knowledge Base**: LLM-powered RAG for hotel AI agent
- **WhatsApp Integration**: Baileys Gateway (local, multi-tenant)
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
- **WhatsApp**: Baileys Gateway
- **Weather**: OpenWeatherMap API
- **Testing**: pytest + pytest-asyncio

### Frontend
- **Framework**: Next.js 14+ (App Router)
- **Styling**: Tailwind CSS
- **Animations**: Framer Motion
- **State**: React Context + Hooks

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/Hammadwakeel/whatsapp-backend.avishkarai.git
cd whatsapp-backend.avishkarai
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:
```env
SECRET_KEY=your-secret-key-generate-with-openssl-rand-hex-32
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/inika_db
OPENROUTER_API_KEY=sk-or-v1-your-key
TAVILY_API_KEY=tvly-your-key
BAILEYS_GATEWAY_URL=http://localhost:3002
```

### 3. Start Database

```bash
docker compose up -d
```

### 4. Start Backend

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 5. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:3000

### 6. Start Baileys Gateway

```bash
cd scripts/whatsapp-gateway
npm install
npm start
```

Gateway runs on http://localhost:3002

## Project Structure

```
inika-backend/
├── app/                    # Backend (FastAPI)
│   ├── api/               # Route handlers
│   ├── core/              # Config, database, security
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic
│   └── main.py            # App entry point
├── frontend/               # Frontend (Next.js)
│   ├── app/               # Pages (App Router)
│   ├── components/        # Shared components
│   └── lib/               # API client
├── scripts/
│   └── whatsapp-gateway/   # Baileys multi-tenant gateway
├── docs/                  # Documentation
├── docker-compose.yml     # Main services (DB, Backend)
└── tests/                 # Test suites
```

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | 5432 | Main database |
| Backend API | 8000 | FastAPI server |
| Frontend | 3000 | Next.js app |
| Baileys | 3002 | Local WhatsApp gateway |

## Environment Variables

### Required
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key (openssl rand -hex 32) |
| `OPENROUTER_API_KEY` | LLM features (shared across tenants) |
| `TAVILY_API_KEY` | Web search (shared across tenants) |

### WhatsApp
| Variable | Default | Description |
|----------|---------|-------------|
| `BAILEYS_GATEWAY_URL` | http://localhost:3002 | Baileys Gateway URL |
| `BAILEYS_GATEWAY_API_KEY` | - | API key (optional) |

### Optional
| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | anthropic/claude-3-haiku | LLM model |
| `INIKA_API_KEY` | - | External booking API |
| `OPENWEATHER_API_KEY` | - | Weather data |

## WhatsApp Integration

### Connecting WhatsApp
1. Start the Baileys Gateway: `cd scripts/whatsapp-gateway && npm start`
2. Open the frontend at http://localhost:3000
3. Go to WhatsApp page
4. Click "Link with phone number"
5. Scan the QR code with WhatsApp

## API Documentation

| Document | Description |
|----------|-------------|
| `docs/API.md` | Auth, Profile, Agent APIs |
| `docs/INTEGRATION.md` | Frontend integration guide |
| `docs/WIKI.md` | Wiki knowledge base system |
| `docs/WHATSAPP.md` | WhatsApp integration guide |
| `docs/BOOKING.md` | Booking system integration |
| `docs/JOURNEY.md` | Journey module documentation |
| `docs/WEBHOOK.md` | Webhook endpoints |

**Swagger UI**: http://localhost:8000/docs

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
- Session management via Baileys Gateway

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
pytest tests/test_tenant_flow.py -v
pytest tests/test_whatsapp.py -v
pytest tests/test_booking.py -v
pytest tests/test_journey.py -v
pytest tests/ -v
```

## Troubleshooting

### WhatsApp QR Code Not Showing
1. Ensure Baileys Gateway is running: `curl http://localhost:3002/health`
2. Check gateway logs for errors
3. Try deleting session and re-scanning

### Messages Not Being Received
1. Verify webhook URL is accessible from the gateway
2. Check backend logs for incoming webhooks
3. Ensure backend is running on port 8000

### Database Connection Issues
```bash
docker ps | grep postgres
docker compose down -v
docker compose up -d
alembic upgrade head
```

## GitHub

Repository: https://github.com/Hammadwakeel/whatsapp-backend.avishkarai.git
