# Journey Module - Guest Engagement & Smart Messaging

Complete guide for the AI-powered guest journey messaging system.

---

## Table of Contents

1. [Overview](#overview)
2. [Auto Scheduler](#auto-scheduler)
3. [Message Types](#message-types)
4. [Endpoints](#endpoints)
5. [Configuration](#configuration)
6. [Frontend Integration](#frontend-integration)
7. [Message Flow](#message-flow)

---

## Overview

The Journey module provides intelligent, contextual messaging to hotel guests based on:

| Factor | Description |
|--------|-------------|
| **Time** | Morning, breakfast, lunch, dinner, evening messages |
| **Weather** | Contextual suggestions based on current weather |
| **Guest Status** | Due In, Arrived, StayOver, Checkout |
| **AI Conversation** | Full conversational support via WhatsApp |

---

## Auto Scheduler

The Journey module includes a fully autonomous background scheduler that runs messaging jobs automatically without manual intervention.

### How It Works

The scheduler is integrated into the FastAPI app lifecycle:

1. **Startup**: When the backend starts, `init_auto_scheduler()` loads all active Journey configs and schedules jobs
2. **Runtime**: APScheduler runs jobs based on configured times
3. **Config Updates**: When journey config changes, jobs are automatically rescheduled
4. **Shutdown**: Scheduler gracefully stops when the app shuts down

### Scheduled Jobs Per Tenant

| Job ID | Schedule | Description |
|--------|----------|-------------|
| `{tenant_id}_morning` | Configured morning hour | Send morning message |
| `{tenant_id}_breakfast` | Configured breakfast hour | Meal reminder |
| `{tenant_id}_lunch` | Configured lunch hour | Meal reminder |
| `{tenant_id}_dinner` | Configured dinner hour | Meal reminder |
| `{tenant_id}_evening` | Configured evening hour | Evening message |
| `{tenant_id}_due_in_check` | Every 30 min (8 AM - 5 PM) | Check for arriving guests |
| `{tenant_id}_checkout_check` | 10 AM daily | Check for checkout guests |

### Anti-Duplication Protection

The scheduler uses `_active_jobs` tracking to prevent duplicate runs:

```
if self._active_jobs.get(tenant_id):
    return  # Skip if already running
```

### Rate Limiting

Each guest receives a maximum of `max_messages_per_day` messages per day (default: 5). The scheduler checks `JourneyMessageLog` before sending.

### Files

- `app/services/journey/auto_scheduler.py` - Main scheduler implementation
- `app/services/journey/__init__.py` - Exports scheduler functions
- `app/main.py` - Scheduler lifecycle integration

### Testing

```bash
# Run auto scheduler tests
python -m pytest tests/test_journey_auto_scheduler.py -v

# All Journey tests
python -m pytest tests/test_journey.py tests/test_journey_auto_scheduler.py -v
```

---

## Message Types

### Time-Based Messages

| Type | Time | Example |
|------|------|---------|
| `breakfast` | 7 AM | "Good morning! Breakfast is served until 10:30 AM. Today's special: pancakes 🥞" |
| `lunch` | 11 AM | "Lunch time! Our chef recommends the grilled salmon. Poolside dining available ☀️" |
| `dinner` | 6 PM | "Dinner is ready! Tonight: Mediterranean night at the rooftop restaurant 🍽️" |
| `evening` | 8 PM | "Evening update: Live music at the lobby bar from 9 PM 🎵" |
| `morning` | 8 AM | "Good morning! It's sunny today - perfect for the pool! ☀️🏊" |

### Status-Based Messages

| Type | Trigger | Example |
|------|---------|---------|
| `due_in` | Guest arriving soon | "We look forward to welcoming you tomorrow! Your room with garden view is ready 🌿" |
| `welcome` | Guest just arrived | "Welcome to Hotel Paradise, [Name]! Room 305 is ready. Pool opens at 7 AM ☀️" |
| `checkout` | Guest leaving today | "Checking out today? Late checkout available until 2 PM. Thank you for staying with us! 🙏" |
| `feedback` | After checkout | "Thank you for staying with us! We'd love to hear about your experience 🏨" |

### Weather-Based Context

| Condition | Message Adaptation |
|-----------|-------------------|
| ☀️ Sunny | "Perfect day for the pool!" |
| 🌧️ Rainy | "Indoor spa and cooking class available!" |
| ❄️ Cold | "Try our warm soup menu and hot tub spa!" |
| ☁️ Cloudy | "Garden walk and indoor café recommended" |

---

## Endpoints

### Configuration

#### Get Journey Config
```
GET /journey/config
Authorization: Bearer <token>

Response:
{
  "id": "uuid",
  "tenant_id": "uuid",
  "is_enabled": true,
  "hotel_city": "Lahore",
  "morning_message_hour": 8,
  "breakfast_hour": 7,
  "lunch_hour": 11,
  "dinner_hour": 18,
  "evening_hour": 20,
  "enable_weather_based": true,
  "enable_meal_reminders": true,
  "enable_status_messages": true,
  "include_due_in": true,
  "include_arrived": true,
  "include_stayover": true,
  "include_checkout_today": true
}
```

#### Update Config
```
POST /journey/config
Authorization: Bearer <token>

Body:
{
  "hotel_city": "Karachi",
  "enable_weather_based": true,
  "morning_message_hour": 9
}
```

#### Enable/Disable
```
POST /journey/config/enable
POST /journey/config/disable
```

---

### Weather

```
GET /journey/weather?city=Lahore
GET /journey/weather?lat=31.5&lon=74.3

Response:
{
  "status": "ok",
  "temperature": 28,
  "condition": "Clear",
  "description": "clear sky",
  "city": "Lahore"
}
```

---

### Guest Management

```
GET /journey/guests
GET /journey/guests?status=Arrived,StayOver

Response:
{
  "guests": [
    {
      "id": "booking-123",
      "gname": "John Doe",
      "room": "305",
      "mobile": "+923001234567",
      "gstatus": "StayOver",
      "cindate": "2024-01-15",
      "coutdate": "2024-01-18"
    }
  ],
  "total": 5
}
```

---

### Message Sending

#### Send to Single Guest
```
POST /journey/send
Authorization: Bearer <token>

Body:
{
  "guest_id": "booking-123",
  "message_type": "morning"
}

Response:
{
  "status": "ok",
  "message_id": "msg-123",
  "sent_to": "923001234567"
}
```

#### Broadcast to All Guests
```
POST /journey/send/broadcast?message_type=morning

Response:
{
  "timestamp": "2024-01-16T08:00:00",
  "message_type": "morning",
  "weather": {...},
  "guests_count": 15,
  "messages_sent": 14,
  "errors": []
}
```

#### Send Welcome Message
```
POST /journey/send/welcome/{guest_id}

Response:
{
  "message": "Welcome to Hotel Paradise, John!...",
  "status": "ok"
}
```

#### Send Due In Messages
```
POST /journey/send/due-in
```

---

### Message Logs

```
GET /journey/logs?limit=50&offset=0&message_type=morning

Response:
{
  "logs": [
    {
      "id": "log-123",
      "guest_name": "John Doe",
      "guest_mobile": "+923001234567",
      "room_number": "305",
      "message_type": "morning",
      "direction": "outbound",
      "content": "Good morning! It's sunny today...",
      "sent_at": "2024-01-16T08:00:00",
      "delivered": true,
      "created_at": "2024-01-16T08:00:00"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

---

### AI Conversation

```
POST /journey/conversation?tenant_id=<uuid>&mobile=<phone>&message=<text>

Response:
{
  "response": "Good afternoon, John! The pool is open until 9 PM...",
  "guest_name": "John Doe",
  "room": "305",
  "wiki_context": "Pool hours: 7 AM - 9 PM..."
}
```

---

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key for weather data |

### Config Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `is_enabled` | bool | true | Enable/disable all journey messaging |
| `hotel_city` | string | "Lahore" | City for weather lookup |
| `hotel_lat/lon` | float | null | Alternative to city for weather |
| `morning_message_hour` | int | 8 | When to send morning message (0-23) |
| `breakfast_hour` | int | 7 | Breakfast reminder time |
| `lunch_hour` | int | 11 | Lunch announcement time |
| `dinner_hour` | int | 18 | Dinner announcement time |
| `evening_hour` | int | 20 | Evening message time |
| `enable_weather_based` | bool | true | Use weather for message content |
| `max_messages_per_day` | int | 5 | Max messages per guest per day |

---

## Frontend Integration

### React - Journey Dashboard

```jsx
import { useState, useEffect } from 'react';

export default function JourneyDashboard() {
  const [config, setConfig] = useState(null);
  const [guests, setGuests] = useState([]);
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [configRes, guestsRes, weatherRes] = await Promise.all([
        fetch('/journey/config', { headers: getAuthHeaders() }),
        fetch('/journey/guests', { headers: getAuthHeaders() }),
        fetch('/journey/weather', { headers: getAuthHeaders() }),
      ]);

      setConfig(await configRes.json());
      setGuests((await guestsRes.json()).guests);
      setWeather(await weatherRes.json());
      setLoading(false);
    } catch (err) {
      console.error('Failed to load:', err);
    }
  };

  const toggleJourney = async (enable) => {
    const url = enable ? '/journey/config/enable' : '/journey/config/disable';
    await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    loadData();
  };

  const broadcastMessage = async (type) => {
    const res = await fetch(`/journey/send/broadcast?message_type=${type}`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    const result = await res.json();
    alert(`Sent ${result.messages_sent} messages`);
    loadData(); // Refresh
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div className="journey-dashboard">
      <h2>Journey Messaging</h2>

      {/* Status Card */}
      <div className="status-card">
        <h3>Current Status</h3>
        <p>Enabled: {config?.is_enabled ? '✅ Yes' : '❌ No'}</p>
        <p>Active Guests: {guests.length}</p>
        {weather?.status === 'ok' && (
          <p>Weather: {weather.temperature}°C, {weather.condition}</p>
        )}
        <button onClick={() => toggleJourney(!config?.is_enabled)}>
          {config?.is_enabled ? 'Disable' : 'Enable'} Journey
        </button>
      </div>

      {/* Quick Actions */}
      <div className="quick-actions">
        <h3>Send Messages</h3>
        <button onClick={() => broadcastMessage('morning')}>
          Send Morning Message
        </button>
        <button onClick={() => broadcastMessage('lunch')}>
          Send Lunch Reminder
        </button>
        <button onClick={() => broadcastMessage('dinner')}>
          Send Dinner Invitation
        </button>
      </div>

      {/* Guest List */}
      <div className="guest-section">
        <h3>Active Guests ({guests.length})</h3>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Room</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {guests.map(guest => (
              <tr key={guest.id}>
                <td>{guest.gname}</td>
                <td>{guest.room}</td>
                <td>{guest.gstatus}</td>
                <td>
                  <button onClick={() => sendWelcome(guest.id)}>
                    Send Welcome
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

### React - Send Message to Guest

```jsx
const sendMessageToGuest = async (guestId, messageType) => {
  const response = await fetch('/journey/send', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      guest_id: guestId,
      message_type: messageType
    })
  });

  const result = await response.json();

  if (result.status === 'ok') {
    alert('Message sent successfully!');
  } else {
    alert('Failed to send: ' + result.error);
  }
};
```

---

## Message Flow

### Automated Message Cycle (Auto Scheduler)

```
1. APScheduler triggers job at configured time
   ↓
2. Check _active_jobs to prevent duplicates
   ↓
3. Get JourneyConfig for tenant
   ↓
4. Fetch current weather (OpenWeatherMap)
   ↓
5. Get active guests from booking system
   ↓
6. For each guest:
   a. Check rate limiting (max 5/day via JourneyMessageLog)
   b. Generate contextual message (AI + weather + wiki)
   c. Send via WhatsApp (Evolution API)
   d. Log message to JourneyMessageLog
   ↓
7. Reset active flag for tenant
```

### Manual Broadcast (API)

```
1. Admin calls POST /journey/send/broadcast
   ↓
2. JourneyScheduler.run_journey_cycle()
   ↓
3. (Same as step 3-7 above)
```

### Incoming Message Flow

```
1. Guest sends WhatsApp message
   ↓
2. Evolution API forwards to /webhook/whatsapp
   ↓
3. Find guest by mobile number (Booking API)
   ↓
4. Generate AI response (with RAG from wiki)
   ↓
5. Send response via Evolution API
   ↓
6. Log conversation to JourneyConversation/JourneyMessage
```

---

## Database Models

### JourneyConfig
Per-tenant configuration for messaging behavior.

### JourneyMessageLog
All sent/received messages with metadata.

### JourneyConversation
Guest conversation threads.

### JourneyMessage
Individual messages in conversations.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Guest has no mobile | Missing phone in booking | Check booking API |
| WhatsApp send failed | Evolution API issue | Check Evolution API status |
| Weather API error | Invalid API key | Check OPENWEATHER_API_KEY |
| No guests | No active bookings | Sync guests from booking API |

---

## Security Notes

1. **Multi-tenant isolation**: Each tenant sees only their guests and messages
2. **Rate limiting**: Max 5 messages per guest per day (configurable)
3. **Opt-out**: Can disable via config endpoint
4. **Message logging**: All messages logged for compliance