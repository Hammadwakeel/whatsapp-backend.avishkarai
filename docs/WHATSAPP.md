# WhatsApp Integration

This document describes the WhatsApp integration using the Baileys Gateway.

## Overview

WhatsApp integration is handled by the Baileys Gateway — a local Node.js service that manages WhatsApp sessions per tenant.

## Quick Start

### 1. Install and run the gateway

```bash
cd scripts/whatsapp-gateway
npm install
npm start
```

The gateway starts on port 3002.

### 2. Configure the backend

Add to your `.env`:

```bash
BAILEYS_GATEWAY_URL=http://localhost:3002
```

### 3. Link WhatsApp

1. Open the WhatsApp page in your dashboard
2. Click "Link with phone number"
3. Scan the QR code (also shown in the gateway terminal)

## Architecture

```
┌─────────────────┐     ┌───────────────┐     ┌──────────────────┐
│  WhatsApp User  │────▶│  Baileys      │────▶│  Inika Backend   │
│                 │◀────│  Gateway       │◀────│                  │
└─────────────────┘     └───────────────┘     └──────────────────┘
                              │                      │
                              │   Webhook           │ AI Response
                              │   POST /webhook/whatsapp-baileys?tenant_id=xxx
                              ▼                      ▼
```

## Per-Tenant Sessions

Each hotel (tenant) gets its own WhatsApp session:
- Session name: `inika-{first_8_chars_of_tenant_id_hash}`
- Sessions stored in `scripts/whatsapp-gateway/sessions/`
- Messages routed via `tenant_id` query parameter

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BAILEYS_GATEWAY_URL` | Baileys Gateway URL | http://localhost:3002 |
| `BAILEYS_GATEWAY_API_KEY` | API key (optional) | - |

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
