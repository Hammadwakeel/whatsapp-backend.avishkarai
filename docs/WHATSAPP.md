# WhatsApp Integration - Frontend Guide

Complete guide for integrating WhatsApp features into your frontend application.

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Endpoints](#endpoints)
4. [Frontend Components](#frontend-components)
5. [Webhooks](#webhooks)
6. [Error Handling](#error-handling)

---

## Overview

| Item | Value |
|------|-------|
| Base URL | `http://localhost:8000` |
| Auth Required | Yes (JWT Bearer token) |
| WhatsApp Gateway | Evolution API |
| API Prefix | `/whatsapp` |

---

## Authentication

All WhatsApp endpoints require JWT authentication. Include the access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Token is obtained from `/auth/login` or `/auth/register`.

---

## Endpoints

### 1. Get Connection Status

Check if WhatsApp is connected.

**Endpoint**: `GET /whatsapp/status`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "is_connected": false,
  "status": "disconnected",
  "phone_number": null,
  "display_name": null,
  "session_id": "uuid"
}
```

| Field | Type | Description |
|-------|------|-------------|
| is_connected | boolean | Whether WhatsApp is linked |
| status | string | disconnected, connecting, connected |
| phone_number | string/null | Connected phone number |
| display_name | string/null | WhatsApp display name |
| session_id | string | Local session identifier |

---

### 2. Connect WhatsApp (Generate QR)

Start WhatsApp connection by generating a QR code.

**Endpoint**: `POST /whatsapp/connect`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK - QR available):
```json
{
  "status": "qr_available",
  "qr_code": "base64_encoded_qr_image",
  "message": "Scan this QR code with WhatsApp",
  "local_session_id": "uuid"
}
```

**Response** (200 OK - Already connected):
```json
{
  "status": "connected",
  "message": "WhatsApp is already connected",
  "connected": true
}
```

**Response** (200 OK - Waiting for QR):
```json
{
  "status": "waiting",
  "message": "Generating QR code...",
  "evolution_url": "http://localhost:8080",
  "instance_name": "inika",
  "local_session_id": "uuid"
}
```

---

### 3. Get QR Code Info

Get current QR code status and data.

**Endpoint**: `GET /whatsapp/qr`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "status": "qr_available",
  "qr_code": "base64_encoded_qr_image",
  "qr_image": "base64_encoded_qr_image",
  "message": "QR code ready"
}
```

---

### 4. Get QR Code as Image

Get QR code as PNG image.

**Endpoint**: `GET /whatsapp/qr/image`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response**: PNG image file

**Example**:
```html
<img src="/whatsapp/qr/image" alt="WhatsApp QR Code" />
```

---

### 5. Disconnect WhatsApp

Disconnect current WhatsApp session.

**Endpoint**: `POST /whatsapp/disconnect`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "message": "WhatsApp disconnected successfully"
}
```

---

### 6. Get WhatsApp Session

Get or create local WhatsApp session.

**Endpoint**: `GET /whatsapp/session`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "status": "disconnected",
  "phone_number": null,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

---

### 7. Get Messages

Get message history with pagination.

**Endpoint**: `GET /whatsapp/messages`

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | Page number |
| page_size | int | 50 | Items per page (max 100) |
| direction | string | null | Filter: `inbound` or `outbound` |

**Headers**:
```
Authorization: Bearer <access_token>
```

**Example**: `GET /whatsapp/messages?page=1&page_size=20&direction=inbound`

**Response** (200 OK):
```json
{
  "messages": [
    {
      "id": "uuid",
      "session_id": "uuid",
      "message_id": "external_message_id",
      "direction": "inbound",
      "from_number": "+1234567890",
      "to_number": "+0987654321",
      "content": "Hello, I need help with my reservation",
      "agent_response": "I'd be happy to help with your reservation...",
      "wiki_sources": {"sources": ["page-1", "page-2"]},
      "web_search_used": false,
      "is_read": false,
      "created_at": "2024-01-01T12:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 50
}
```

---

### 8. Webhook Configuration (Receive Messages)

Endpoint for Evolution API to send incoming messages.

**Endpoint**: `POST /whatsapp/webhook`

**Headers**: None required (configured externally)

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
        "id": "message_id"
      },
      "message": {
        "conversation": "Hello, I need help"
      }
    }
  }
}
```

**Response**:
```json
{
  "status": "ok",
  "processed": true
}
```

---

## Frontend Components

### React - WhatsApp Connection Manager

```jsx
import { useState, useEffect } from 'react';

export default function WhatsAppManager() {
  const [status, setStatus] = useState(null);
  const [qrImage, setQrImage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  });

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const response = await fetch('/whatsapp/status', {
        headers: getAuthHeaders()
      });
      const data = await response.json();
      setStatus(data);
      setLoading(false);

      if (!data.is_connected) {
        fetchQRCode();
      }
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const fetchQRCode = async () => {
    try {
      const response = await fetch('/whatsapp/qr', {
        headers: getAuthHeaders()
      });
      const data = await response.json();

      if (data.qr_code) {
        setQrImage(`data:image/png;base64,${data.qr_code}`);
      }
    } catch (err) {
      console.error('Failed to fetch QR:', err);
    }
  };

  const connect = async () => {
    try {
      const response = await fetch('/whatsapp/connect', {
        method: 'POST',
        headers: getAuthHeaders()
      });
      const data = await response.json();

      if (data.qr_code) {
        setQrImage(`data:image/png;base64,${data.qr_code}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const disconnect = async () => {
    if (!confirm('Disconnect WhatsApp?')) return;

    try {
      await fetch('/whatsapp/disconnect', {
        method: 'POST',
        headers: getAuthHeaders()
      });
      checkStatus();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="whatsapp-manager">
      <h2>WhatsApp Connection</h2>

      {status?.is_connected ? (
        <div className="connected">
          <p>✅ WhatsApp Connected</p>
          <p>Phone: {status.phone_number}</p>
          <p>Status: {status.status}</p>
          <button onClick={disconnect}>Disconnect</button>
        </div>
      ) : (
        <div className="disconnected">
          <p>❌ WhatsApp Not Connected</p>

          {qrImage ? (
            <div className="qr-container">
              <img src={qrImage} alt="Scan this QR" />
              <p>Scan with WhatsApp → Linked Devices → Link a Device</p>
              <button onClick={fetchQRCode}>Refresh QR</button>
            </div>
          ) : (
            <button onClick={connect}>Generate QR Code</button>
          )}
        </div>
      )}
    </div>
  );
}
```

### React - Message History

```jsx
import { useState, useEffect } from 'react';

export default function MessageHistory() {
  const [messages, setMessages] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState('all');

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  });

  useEffect(() => {
    fetchMessages();
  }, [page, filter]);

  const fetchMessages = async () => {
    const direction = filter === 'all' ? '' : `&direction=${filter}`;
    const response = await fetch(
      `/whatsapp/messages?page=${page}&page_size=20${direction}`,
      { headers: getAuthHeaders() }
    );
    const data = await response.json();
    setMessages(data.messages);
    setTotal(data.total);
  };

  return (
    <div className="message-history">
      <h2>Message History</h2>

      <div className="filters">
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All Messages</option>
          <option value="inbound">Inbound Only</option>
          <option value="outbound">Outbound Only</option>
        </select>

        <span>Page {page} of {Math.ceil(total / 20)}</span>

        <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
          Previous
        </button>
        <button disabled={page * 20 >= total} onClick={() => setPage(p => p + 1)}>
          Next
        </button>
      </div>

      <div className="messages">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`message ${msg.direction}`}
          >
            <span className="direction">{msg.direction}</span>
            <span className="from">{msg.from_number}</span>
            <p className="content">{msg.content}</p>
            {msg.agent_response && (
              <p className="response"><strong>AI Response:</strong> {msg.agent_response}</p>
            )}
            <span className="time">{new Date(msg.created_at).toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Vue 3 - WhatsApp Composable

```javascript
// composables/useWhatsApp.js
import { ref } from 'vue';

export function useWhatsApp() {
  const status = ref(null);
  const qrCode = ref(null);
  const loading = ref(false);
  const error = ref(null);

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  });

  const checkStatus = async () => {
    loading.value = true;
    try {
      const response = await fetch('/whatsapp/status', {
        headers: getAuthHeaders()
      });
      status.value = await response.json();
    } catch (err) {
      error.value = err.message;
    }
    loading.value = false;
  };

  const connect = async () => {
    loading.value = true;
    try {
      const response = await fetch('/whatsapp/connect', {
        method: 'POST',
        headers: getAuthHeaders()
      });
      const data = await response.json();

      if (data.qr_code) {
        qrCode.value = `data:image/png;base64,${data.qr_code}`;
      }
    } catch (err) {
      error.value = err.message;
    }
    loading.value = false;
  };

  const disconnect = async () => {
    loading.value = true;
    try {
      await fetch('/whatsapp/disconnect', {
        method: 'POST',
        headers: getAuthHeaders()
      });
      await checkStatus();
    } catch (err) {
      error.value = err.message;
    }
    loading.value = false;
  };

  return {
    status,
    qrCode,
    loading,
    error,
    checkStatus,
    connect,
    disconnect
  };
}
```

---

## Webhooks

### Incoming Messages

When a customer sends a WhatsApp message:

1. Evolution API forwards it to `/whatsapp/webhook`
2. Backend records the message
3. AI agent generates a response
4. Response is sent back via Evolution API to the customer

### Webhook Response Format

The webhook endpoint returns:
```json
{
  "message": "Response text from AI agent",
  "agent_response": "Response text from AI agent",
  "sources": ["page-1", "page-2"],
  "success": true
}
```

---

## Error Handling

### Common Errors

| Status | Error | Solution |
|--------|-------|----------|
| 401 | Not authenticated | Login and include token |
| 404 | Session not found | Call `/whatsapp/connect` first |
| 500 | Evolution API error | Check Evolution API is running |

### Connection Issues

1. **QR not showing**: Call `POST /whatsapp/connect` to regenerate
2. **Connection drops**: Check Evolution API logs
3. **Messages not received**: Verify webhook is configured

### Status Polling

For real-time updates, poll `/whatsapp/status` every 5 seconds during QR scanning:

```javascript
// Poll status until connected
const pollStatus = async () => {
  const interval = setInterval(async () => {
    const response = await fetch('/whatsapp/status', {
      headers: getAuthHeaders()
    });
    const data = await response.json();

    if (data.is_connected) {
      clearInterval(interval);
      // Connected!
    }
  }, 5000);
};
```

---

## Multi-Tenant Isolation

Each tenant has isolated WhatsApp data:
- Hotel A's messages are not visible to Hotel B
- `tenant_id` is extracted from JWT token
- Sessions are created per tenant

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EVOLUTION_URL` | Evolution API URL | http://localhost:8080 |
| `EVOLUTION_API_KEY` | API authentication key | - |
| `EVOLUTION_INSTANCE_NAME` | Instance name | inika |