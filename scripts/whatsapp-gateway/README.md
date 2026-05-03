# Inika WhatsApp Gateway (Baileys)

Multi-tenant WhatsApp gateway using [WhiskeySockets/Baileys](https://github.com/WhiskeySockets/Baileys) - the official open-source WhatsApp Web API library.

## Features

- Multi-tenant WhatsApp sessions (one session per tenant)
- QR code generation for WhatsApp linking
- Webhook support for incoming messages
- Automatic session persistence and reconnection
- REST API for all operations
- API key authentication
- Proper logging with Pino

## Official Baileys Documentation

- **Library**: [WhiskeySockets/Baileys](https://github.com/WhiskeySockets/Baileys)
- **Docs**: [baileys.wiki](https://baileys.wiki)
- **Discord**: [Join here](https://discord.gg/WeJM5FP9GG)
- **Migration to v7**: [baileys.wiki/docs/migration/to-v7.0.0](https://baileys.wiki/docs/migration/to-v7.0.0)

## Quick Start

### 1. Install dependencies

```bash
cd scripts/whatsapp-gateway
npm install
```

### 2. Configure environment

Create a `.env` file:

```env
PORT=3002
SESSIONS_DIR=./sessions
WEBHOOK_URL=http://localhost:8000/webhook/whatsapp-baileys
API_KEY=your-secret-api-key
LOG_LEVEL=info
```

### 3. Start the gateway

```bash
npm start
```

The gateway will start on port 3002.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (no auth) |
| `/api/sessions` | GET | List all sessions |
| `/api/sessions/:name` | GET | Get session status |
| `/api/sessions/:name/qr` | GET | Get QR code |
| `/api/sessions` | POST | Create session |
| `/api/sessions/:name/start` | POST | Start/resume session |
| `/api/sessions/:name` | DELETE | Delete session (logout) |
| `/api/messages/sendText` | POST | Send message |

### Authentication

All `/api/*` endpoints require `x-api-key` header:

```bash
curl -H "x-api-key: your-api-key" http://localhost:3002/api/sessions
```

## Session Format

Each tenant gets their own session with name format: `inika-{hash_suffix}`

Where `hash_suffix` is the first 8 characters of the MD5 hash of the tenant ID.

## Example Usage

### Create a session
```bash
curl -X POST http://localhost:3002/api/sessions \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"name": "inika-abc12345"}'
```

### Get QR code
```bash
curl http://localhost:3002/api/sessions/inika-abc12345/qr \
  -H "x-api-key: your-api-key"
```

### Send message
```bash
curl -X POST http://localhost:3002/api/messages/sendText \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{"session": "inika-abc12345", "chatId": "923001234567", "text": "Hello!"}'
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  WhatsApp User  │────▶│  Baileys        │────▶│  Inika Backend   │
│                 │◀────│  Gateway        │◀────│                  │
└─────────────────┘     └─────────────────┘     └──────────────────┘
                              │                      │
                              │   Webhook           │ AI Response
                              │   POST /webhook/whatsapp-baileys?tenant_id=xxx
                              ▼                      ▼
```

## Official Baileys Patterns Used

### 1. Auth State Management
```javascript
const { state, saveCreds } = await useMultiFileAuthState(sessionPath);

const sock = makeWASocket({
  auth: {
    creds: state.creds,
    keys: makeCacheableSignalKeyStore(state.keys, logger),
  },
});

// Save credentials on every update (REQUIRED)
sock.ev.on('creds.update', saveCreds);
```

### 2. Connection Handling with DisconnectReason
```javascript
sock.ev.on('connection.update', async (update) => {
  const { connection, lastDisconnect } = update;

  if (connection === 'close') {
    const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
    if (shouldReconnect) {
      await connectToWhatsApp(tenantId);
    }
  }
});
```

### 3. Message Handling
```javascript
sock.ev.on('messages.upsert', async ({ messages }) => {
  for (const msg of messages) {
    if (msg.key.fromMe) continue;
    // Process message
  }
});
```

### 4. Browser Configuration
```javascript
import { Browsers } from '@whiskeysockets/baileys';

const sock = makeWASocket({
  browser: Browsers.ubuntu('Inika WhatsApp Gateway'),
});
```

## Troubleshooting

### QR code not showing
1. Check if the gateway is running: `curl http://localhost:3002/health`
2. Check the terminal output for QR code
3. Make sure port 3002 is not in use

### Messages not being received
1. Verify webhook URL is correct in the backend config
2. Check backend logs for incoming webhooks
3. Ensure the backend is running and accessible

### Session disconnected
1. Delete the session: `DELETE /api/sessions/:name`
2. Create a new session: `POST /api/sessions`
3. Scan the new QR code

### Auth state issues
If you get "not logged in" errors:
1. Delete the session folder in `./sessions/`
2. Create a new session
3. Scan the QR code again

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 3002 | Server port |
| `SESSIONS_DIR` | ./sessions | Where to store auth files |
| `WEBHOOK_URL` | http://localhost:8000/webhook/whatsapp-baileys | Backend webhook URL |
| `API_KEY` | (none) | API key for authentication |
| `LOG_LEVEL` | info | Logging level (debug, info, warn, error) |