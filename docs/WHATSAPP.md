# WhatsApp Integration

This document describes the WhatsApp integration using the Baileys Gateway, WAHA, or Evolution API.

## Overview

The system integrates with WhatsApp through a gateway that handles:
- QR code generation for linking your WhatsApp account
- Receiving incoming messages via webhooks
- Sending outbound messages
- Connection status monitoring

## Supported Gateways

### 1. Baileys Gateway (Recommended for Development)

A local Node.js gateway using the Baileys library. Simple to set up, runs on your machine.

- **Location**: `scripts/whatsapp-gateway/`
- **Features**: Fast setup, multi-tenant, runs locally

```bash
# Install and run
cd scripts/whatsapp-gateway
npm install
npm start
```

### 2. WAHA (Production Ready)

A Docker-based production-ready WhatsApp gateway.

- **Repository**: https://github.com/devofmind/waha
- **Documentation**: https://waha.tech/docs

```bash
# Start with Docker
docker compose -f docker-compose.waha.yml up -d
```

### 3. Evolution API (Deprecated)

Legacy option, no longer recommended.

## Quick Start with Baileys Gateway

### 1. Install dependencies

```bash
cd scripts/whatsapp-gateway
npm install
```

### 2. Start the gateway

```bash
npm start
```

The gateway will start on port 3002 with QR codes printed to the terminal.

### 3. Configure backend

Add to your `.env`:

```bash
BAILEYS_GATEWAY_URL=http://localhost:3002
```

### 4. Link WhatsApp

1. Open the WhatsApp page in your dashboard
2. Click "Link with phone number"
3. Scan the QR code (also shown in terminal)

## Architecture

```
┌─────────────────┐     ┌───────────────┐     ┌──────────────────┐
│  WhatsApp User  │────▶│  Baileys       │────▶│  Inika Backend   │
│                 │◀────│  Gateway       │◀────│                  │
└─────────────────┘     └───────────────┘     └──────────────────┘
                              │                      │
                              │   Webhook           │ AI Response
                              │   POST /webhook/whatsapp-baileys?tenant_id=xxx
                              ▼                      ▼
```

## Per-Tenant Sessions

Each hotel (tenant) gets their own WhatsApp session:
- Session name: `inika-{first_8_chars_of_tenant_id_hash}`
- Sessions are stored in `scripts/whatsapp-gateway/sessions/`
- Messages are routed using the `tenant_id` query parameter

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BAILEYS_GATEWAY_URL` | Baileys Gateway URL | http://localhost:3002 |
| `BAILEYS_GATEWAY_API_KEY` | API key (optional) | - |
| `WAHA_URL` | WAHA URL (if using WAHA) | http://localhost:3001 |
| `WAHA_API_KEY` | WAHA API key (optional) | - |
| `EVOLUTION_URL` | Evolution URL (deprecated) | http://localhost:8080 |

## Gateway Priority

If multiple gateways are configured, the system uses them in this order:
1. Baileys Gateway
2. WAHA
3. Evolution API (fallback)

## API Endpoints

### Backend WhatsApp API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/whatsapp/status` | GET | Get connection status |
| `/whatsapp/connect` | POST | Generate QR code |
| `/whatsapp/disconnect` | POST | Disconnect WhatsApp |
| `/whatsapp/reset-session` | GET | Reset and reconnect |
| `/whatsapp/refresh-webhook` | POST | Refresh webhook config |
| `/whatsapp/send` | POST | Send a message |
| `/whatsapp/messages` | GET | Get message history |
| `/whatsapp/events` | GET | SSE for real-time updates |

### Baileys Gateway API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /health` | Health check | |
| `GET /api/sessions` | List all sessions | |
| `GET /api/sessions/:name` | Get session status | |
| `GET /api/sessions/:name/qr` | Get QR code | |
| `POST /api/sessions` | Create session | |
| `POST /api/sessions/:name/start` | Start/resume session | |
| `DELETE /api/sessions/:name` | Delete session | |
| `POST /api/messages/sendText` | Send message | |

## Message Flow

1. **Inbound**: WhatsApp → Baileys Gateway → Webhook → Backend → AI Agent → Response → Baileys Gateway → WhatsApp User
2. **Outbound**: Dashboard → Backend → Baileys Gateway → WhatsApp User

## Troubleshooting

### QR Code Not Appearing

1. Ensure Baileys Gateway is running: `curl http://localhost:3002/health`
2. Check the terminal for QR code (printed there too)
3. Verify `BAILEYS_GATEWAY_URL` is correct

### Messages Not Being Received

1. Verify webhook URL is accessible from the gateway
2. Check backend logs for incoming webhooks
3. Ensure the backend is running on port 8000

### Session Disconnected

1. Click "Reset & Reconnect" in the WhatsApp page
2. This will generate a new QR code
3. Re-scan with WhatsApp