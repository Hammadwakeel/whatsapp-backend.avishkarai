# WhatsApp Integration - Evolution API

## Overview

This document describes the WhatsApp integration using **Evolution API**, a free and open-source WhatsApp gateway solution.

## Why Evolution API?

| Feature | Benefit |
|---------|---------|
| ✅ Free & Open Source | No costs |
| ✅ REST API | Easy to integrate |
| ✅ Webhook Support | Real-time message handling |
| ✅ Docker Support | Easy deployment |
| ✅ Multi-instance | Support for multiple tenants |
| ✅ QR via API | No UI needed |

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Your Frontend  │────▶│  Inika Backend   │────▶│  Evolution API  │
│  (React/Next.js) │     │  (FastAPI)       │     │  (Docker)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                         │
                               │                         ▼
                               │                  ┌─────────────────┐
                               │                  │   WhatsApp      │
                               │                  │   (QR Scan)     │
                               │                  └─────────────────┘
                               ▼
                        ┌─────────────────┐
                        │   PostgreSQL    │
                        │   (Sessions)    │
                        └─────────────────┘
```

## Setup

### 1. Start Evolution API

```bash
# Using Docker Compose (included in project)
docker-compose -f docker-compose.evolution.yml up -d

# Or manually with Docker
docker run -d \
  --name evolution-api \
  -p 8080:8080 \
  -e SERVER_URL=http://localhost:8080 \
  -e AUTHENTICATION_API_KEY=your-secure-api-key \
  -v evolution-data:/evolution/instances \
  atendai/evolution-api:latest
```

### 2. Configure Environment Variables

Add these to your `.env` file:

```env
# Evolution API Configuration
EVOLUTION_URL=http://localhost:8080
EVOLUTION_API_KEY=your-secure-api-key
EVOLUTION_INSTANCE_NAME=inika
```

### 3. Create Instance in Evolution API

```bash
# Create a new instance
curl -X POST http://localhost:8080/instance/create \
  -H "apikey: your-secure-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "inika",
    "integration": "WHATSAPP-BAILEY"
  }'
```

### 4. Connect Webhook

Point Evolution API webhook to your backend:

```bash
# Set webhook URL
curl -X POST http://localhost:8080/webhook/set \
  -H "apikey: your-secure-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "url": "https://your-backend-url.com/whatsapp/webhook",
      "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]
    }
  }'
```

## API Endpoints

### Get QR Code
```
GET /api/v1/whatsapp/qr
Authorization: Bearer <tenant_token>

Response:
{
  "status": "qr_available",
  "qr_code": "base64_encoded_qr_image",
  "message": "Scan this QR code with WhatsApp"
}
```

### Get QR as Image
```
GET /api/v1/whatsapp/qr/image
Authorization: Bearer <tenant_token>

Response: PNG image
```

### Get Connection Status
```
GET /api/v1/whatsapp/status
Authorization: Bearer <tenant_token>

Response:
{
  "is_connected": true,
  "status": "CONNECTED",
  "phone_number": "+1234567890",
  "display_name": "Hotel Name",
  ...
}
```

### Connect WhatsApp
```
POST /api/v1/whatsapp/connect
Authorization: Bearer <tenant_token>

Response:
{
  "status": "qr_available",
  "qr_code": "...",
  "message": "Scan this QR code with WhatsApp"
}
```

### Disconnect WhatsApp
```
POST /api/v1/whatsapp/disconnect
Authorization: Bearer <tenant_token>

Response:
{
  "message": "WhatsApp disconnected successfully"
}
```

### Get Messages
```
GET /api/v1/whatsapp/messages?page=1&page_size=50&direction=inbound
Authorization: Bearer <tenant_token>

Response:
{
  "messages": [...],
  "total": 100,
  "page": 1,
  "page_size": 50
}
```

### Webhook (for Evolution API)
```
POST /api/v1/whatsapp/webhook

This endpoint receives messages from WhatsApp via Evolution API.
Configure this URL in Evolution API dashboard.
```

## Frontend Integration

### React Component Example

```jsx
import { useState, useEffect } from 'react';

export default function WhatsAppQR() {
  const [qrImage, setQrImage] = useState(null);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchQRCode();
  }, []);

  const fetchQRCode = async () => {
    try {
      const response = await fetch('/api/v1/whatsapp/qr', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      const data = await response.json();

      if (data.status === 'qr_available' && data.qr_code) {
        setQrImage(`data:image/png;base64,${data.qr_code}`);
        setStatus('scan');
      } else if (data.status === 'connected') {
        setStatus('connected');
      } else {
        setError(data.message);
        setStatus('error');
      }
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  if (status === 'loading') return <div>Loading...</div>;
  if (status === 'connected') return <div>WhatsApp Connected!</div>;
  if (status === 'error') return <div>Error: {error}</div>;

  return (
    <div>
      <h2>Scan QR Code</h2>
      {qrImage && <img src={qrImage} alt="WhatsApp QR" />}
      <p>Open WhatsApp → Linked Devices → Scan QR</p>
      <button onClick={fetchQRCode}>Refresh QR</button>
    </div>
  );
}
```

### Using the Image Endpoint

```jsx
// Simpler approach - just display the image
<img src="/api/v1/whatsapp/qr/image" alt="WhatsApp QR" />
```

## Multi-Tenant Support

### Option 1: Single WhatsApp (Shared)

All tenants share the same WhatsApp connection. Messages are routed based on phone number.

### Option 2: Per-Tenant WhatsApp (Multiple Instances)

Run multiple Evolution API instances, one per tenant:

```yaml
# docker-compose.yml for multi-tenant
services:
  evolution-tenant1:
    image: atendai/evolution-api:latest
    environment:
      - INSTANCE_NAME=tenant1
    ports:
      - "8081:8080"

  evolution-tenant2:
    image: atendai/evolution-api:latest
    environment:
      - INSTANCE_NAME=tenant2
    ports:
      - "8082:8080"
```

## Troubleshooting

### QR Code Not Showing

1. Check Evolution API is running: `curl http://localhost:8080/health`
2. Check instance exists: `curl http://localhost:8080/instance/connectionState/inika`
3. Check API key is correct in `.env`

### Connection Issues

1. Ensure webhook is properly configured
2. Check Evolution API logs: `docker logs evolution-api`
3. Verify WhatsApp isn't connected elsewhere

### Message Not Received

1. Check webhook URL is publicly accessible
2. Verify webhook events are enabled
3. Check Evolution API dashboard for incoming messages

## Evolution API Documentation

For more details, visit: https://doc.evolution-api.com/

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EVOLUTION_URL` | Evolution API URL | http://localhost:8080 |
| `EVOLUTION_API_KEY` | API Key for authentication | - |
| `EVOLUTION_INSTANCE_NAME` | Instance name | inika |