# Webhook Integration Guide

Guide for integrating webhook endpoints for WhatsApp and external systems.

---

## Table of Contents

1. [Overview](#overview)
2. [Endpoints](#endpoints)
3. [Frontend Integration](#frontend-integration)
4. [External Integration](#external-integration)

---

## Overview

| Item | Value |
|------|-------|
| Base URL | `http://localhost:8000` |
| Auth Required | Varies by endpoint |
| Prefix | `/webhook` |

### Webhook Types

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `/webhook/whatsapp` | Receive WhatsApp messages from Evolution API | None (configured externally) |
| `/webhook/status/{tenant_id}` | Get WhatsApp & Agent status | None |
| `/webhook/health` | Health check | None |

---

## Endpoints

### 1. WhatsApp Message Webhook

Receives incoming WhatsApp messages from Evolution API. This endpoint is configured in Evolution API dashboard.

**Endpoint**: `POST /webhook/whatsapp`

**Authentication**: None ( Evolution API calls this)

**Request Body** (from Evolution API):
```json
{
  "event": "MESSAGES_UPSERT",
  "session": "inika",
  "data": {
    "message": {
      "key": {
        "remoteJid": "1234567890@s.whatsapp.net",
        "fromMe": false,
        "id": "message_id_123"
      },
      "message": {
        "conversation": "Hello, I need help with my reservation"
      },
      "pushName": "John Doe"
    }
  }
}
```

**Response**:
```json
{
  "message": "Hi John! I'd be happy to help with your reservation. Could you please provide your booking reference?",
  "agent_response": "Hi John! I'd be happy to help with your reservation...",
  "sources": ["page-uuid-1"],
  "success": true
}
```

### Flow Diagram

```
Evolution API → /webhook/whatsapp → AI Agent → Response → Customer
                                        ↓
                                   Record Message
                                   (inbound & outbound)
```

### Configuration in Evolution API

```bash
# Set webhook URL
curl -X POST http://localhost:8080/webhook/set \
  -H "apikey: your-secure-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "url": "https://your-backend-url.com/webhook/whatsapp",
      "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]
    }
  }'
```

---

### 2. Status Webhook

Get WhatsApp and Agent status for a tenant.

**Endpoint**: `GET /webhook/status/{tenant_id}`

**Authentication**: None

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| tenant_id | string (UUID) | Tenant ID |

**Response**:
```json
{
  "tenant_id": "uuid",
  "whatsapp": {
    "is_connected": true,
    "status": "CONNECTED",
    "phone_number": "+1234567890"
  },
  "agent": {
    "is_configured": true,
    "has_system_prompt": true
  }
}
```

**Example cURL**:
```bash
curl http://localhost:8000/webhook/status/your-tenant-uuid
```

---

### 3. Health Check

Health check for webhook service.

**Endpoint**: `GET /webhook/health`

**Response**:
```json
{
  "status": "healthy",
  "service": "inika-webhook"
}
```

---

## Frontend Integration

### React - Webhook Status Component

```jsx
import { useState, useEffect } from 'react';

export default function WebhookStatus({ tenantId }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStatus();
  }, [tenantId]);

  const fetchStatus = async () => {
    try {
      const response = await fetch(`/webhook/status/${tenantId}`);
      const data = await response.json();
      setStatus(data);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="webhook-status">
      <h2>System Status</h2>

      <div className="whatsapp-section">
        <h3>WhatsApp</h3>
        <p>Status: {status.whatsapp.status}</p>
        <p>Connected: {status.whatsapp.is_connected ? 'Yes' : 'No'}</p>
        {status.whatsapp.phone_number && (
          <p>Phone: {status.whatsapp.phone_number}</p>
        )}
      </div>

      <div className="agent-section">
        <h3>AI Agent</h3>
        <p>Configured: {status.agent.is_configured ? 'Yes' : 'No'}</p>
        <p>System Prompt: {status.agent.has_system_prompt ? 'Set' : 'Not set'}</p>
      </div>
    </div>
  );
}
```

---

## Message Flow

### Incoming WhatsApp Message

```
1. Customer sends message via WhatsApp
   ↓
2. Evolution API receives message
   ↓
3. Evolution API calls POST /webhook/whatsapp
   ↓
4. Backend records inbound message
   ↓
5. Backend queries AI agent (wiki + web search)
   ↓
6. AI agent generates response
   ↓
7. Backend sends response via Evolution API
   ↓
8. Customer receives reply on WhatsApp
   ↓
9. Backend records outbound message
```

---

## Error Handling

| Status | Error | Solution |
|--------|-------|----------|
| 400 | Invalid payload | Check request body format |
| 404 | Tenant not found | Verify tenant_id |
| 500 | Agent error | Check OpenRouter/Tavily API keys |

---

## Security Notes

1. **Webhook endpoints are public** - They don't require JWT auth
2. **Use tenant_id validation** - External systems must provide valid tenant_id
3. **Rate limiting** - Consider adding rate limits for external queries
4. **API key for production** - Add API key validation for external systems

---

## Production Checklist

- [ ] Verify webhook URL is publicly accessible
- [ ] Configure Evolution API webhook events
- [ ] Set up monitoring for webhook failures
- [ ] Test message flow end-to-end
