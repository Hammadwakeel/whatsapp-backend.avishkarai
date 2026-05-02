# Inika Backend - Multi-Tenant Hotel Platform

Multi-tenant SaaS platform for hotels with WhatsApp AI agent integration.

## Features

- **Multi-Tenant Architecture**: Each hotel (tenant) has isolated data
- **JWT Authentication**: Tenant-based auth with access/refresh tokens
- **Wiki Knowledge Base**: LLM-powered RAG for hotel AI agent
- **WhatsApp Integration**: OpenClaw gateway for WhatsApp sessions
- **Shared API Keys**: OpenRouter, Tavily keys shared across all tenants

## Tech Stack

- **Framework**: FastAPI (async)
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Auth**: JWT with tenant_id isolation
- **LLM**: OpenRouter (Claude) integration
- **Testing**: pytest + pytest-asyncio

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start database
docker-compose up -d

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string |
| SECRET_KEY | Yes | JWT signing key |
| OPENROUTER_API_KEY | Yes | SHARED - LLM features |
| TAVILY_API_KEY | Yes | SHARED - Web search |

## API Documentation

- Swagger UI: `http://localhost:8000/docs`
- Auth API: `docs/API.md`
- Integration Guide: `docs/INTEGRATION.md`
- Wiki System: `docs/WIKI.md`
- WhatsApp: `docs/WHATSAPP.md`
- Webhooks: `docs/WEBHOOK.md`
- Booking: `docs/BOOKING.md`

## GitHub

Repository: https://github.com/Hammadwakeel/whatsapp-backend.avishkarai.git