# Webhook Integration Guide

Guide for integrating webhook endpoints for WhatsApp, Agent queries, and external systems.

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
| `/webhook/agent` | Query AI agent from external systems | None (use API key in body) |
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

### 2. Agent Query Webhook

Query the AI agent from external systems ( chatbots, other apps).

**Endpoint**: `POST /webhook/agent`

**Authentication**: None (API key in request body)

**Request Body**:
```json
{
  "tenant_id": "uuid-of-tenant",
  "query": "What are your check-in times?",
  "session_id": "optional-session-id"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| tenant_id | string (UUID) | Yes | Tenant to query |
| query | string | Yes | Question for the AI |
| session_id | string | No | Session identifier for tracking |

**Response**:
```json
{
  "message": "Check-in time is 3:00 PM and check-out is 11:00 AM.",
  "agent_response": "Check-in time is 3:00 PM...",
  "sources": ["page-uuid-1", "page-uuid-2"],
  "success": true
}
```

**Example cURL**:
```bash
curl -X POST http://localhost:8000/webhook/agent \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-uuid",
    "query": "What are your check-in times?"
  }'
```

---

### 3. Status Webhook

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
    "has_system_prompt": true,
    "has_personality_prompt": false
  }
}
```

**Example cURL**:
```bash
curl http://localhost:8000/webhook/status/your-tenant-uuid
```

---

### 4. Health Check

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
        <p>Connected: {status.whatsapp.is_connected ? '✅ Yes' : '❌ No'}</p>
        {status.whatsapp.phone_number && (
          <p>Phone: {status.whatsapp.phone_number}</p>
        )}
      </div>

      <div className="agent-section">
        <h3>AI Agent</h3>
        <p>Configured: {status.agent.is_configured ? '✅ Yes' : '❌ No'}</p>
        <p>System Prompt: {status.agent.has_system_prompt ? '✅ Set' : '❌ Not set'}</p>
        <p>Personality: {status.agent.has_personality_prompt ? '✅ Set' : '❌ Not set'}</p>
      </div>
    </div>
  );
}
```

---

## External Integration

### Python - Query Agent

```python
import requests

def query_agent(tenant_id: str, query: str):
    """Query the AI agent from external system"""
    response = requests.post(
        "http://localhost:8000/webhook/agent",
        json={
            "tenant_id": tenant_id,
            "query": query
        }
    )

    if response.status_code == 200:
        result = response.json()
        return result["message"], result.get("sources", [])
    else:
        raise Exception(f"Error: {response.text}")

# Usage
answer, sources = query_agent("tenant-uuid", "What amenities do you offer?")
print(answer)
```

### Node.js - Query Agent

```javascript
async function queryAgent(tenantId, query) {
  const response = await fetch('http://localhost:8000/webhook/agent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tenant_id: tenantId,
      query: query
    })
  });

  const data = await response.json();
  return {
    message: data.message,
    sources: data.sources || []
  };
}

// Usage
const { message, sources } = await queryAgent('tenant-uuid', 'What amenities do you offer?');
console.log(message);
```

### cURL - Query Agent

```bash
curl -X POST http://localhost:8000/webhook/agent \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-uuid",
    "query": "What are your check-in times?"
  }'
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

### Query from External System

```
1. External system calls POST /webhook/agent
   ↓
2. Backend verifies tenant exists
   ↓
3. Backend queries AI agent
   ↓
4. AI agent generates response
   ↓
5. Backend returns response
```

---

## Error Handling

| Status | Error | Solution |
|--------|-------|----------|
| 400 | Missing tenant_id or query | Check request body |
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
- [ ] Add rate limiting for `/webhook/agent`
- [ ] Set up monitoring for webhook failures
- [ ] Add API key validation for external access
- [ ] Test message flow end-to-end