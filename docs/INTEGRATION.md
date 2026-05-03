# Integration Guide

Guide for integrating frontend applications with the Inika Backend API.

---

## Overview

- **Architecture**: Multi-Tenant (each hotel = tenant)
- **Auth**: JWT with tenant_id (hotel admin = tenant)
- **API Keys**: SHARED across all tenants (OpenRouter, Tavily)
- **API Base**: `http://localhost:8000`
- **Docs**: `http://localhost:8000/docs`

---

## Multi-Tenant Architecture

In this platform:
- **Tenant = Hotel Admin**: The hotel admin account IS the tenant
- **Data Isolation**: All tenant data has `tenant_id` for isolation
- **Shared API Keys**: OpenRouter, Tavily keys are shared across all tenants

```
Tenant A (Hotel Paradise) ─┐
                           │  Same API Keys
Tenant B (Hotel Sunrise) ─┘  Different Data
```

---

## Quick Start

### 1. Register a Hotel Tenant

```javascript
const registerHotel = async (name, email, password, hotelName) => {
  const response = await fetch("http://localhost:8000/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      email,
      password,
      hotel_name: hotelName
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }

  return response.json(); // Contains access_token, refresh_token, tenant
};
```

### 2. Login as Tenant

```javascript
const login = async (email, password) => {
  const response = await fetch("http://localhost:8000/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }

  const data = await response.json();
  // Store tokens
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  // Store tenant info
  localStorage.setItem("tenant", JSON.stringify(data.tenant));

  return data;
};
```

### 3. Authenticated Requests

```javascript
const getAuthHeaders = () => ({
  "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
  "Content-Type": "application/json"
});

const getProfile = async () => {
  const response = await fetch("http://localhost:8000/auth/profile", {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    if (response.status === 401) {
      // Token expired, try refresh
      await refreshToken();
      return getProfile();
    }
    throw new Error("Failed to fetch profile");
  }

  return response.json(); // Returns tenant profile
};
```

### 4. Token Refresh

```javascript
const refreshToken = async () => {
  const refresh_token = localStorage.getItem("refresh_token");

  const response = await fetch("http://localhost:8000/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token })
  });

  if (!response.ok) {
    // Refresh token expired, redirect to login
    logout();
    throw new Error("Session expired");
  }

  const tokens = await response.json();
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);

  return tokens;
};
```

### 5. Logout

```javascript
const logout = async () => {
  try {
    await fetch("http://localhost:8000/auth/logout", {
      method: "POST",
      headers: getAuthHeaders()
    });
  } finally {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("tenant");
  }
};
```

---

## React Integration Example

### Auth Context (Tenant-Based)

```javascript
// AuthContext.jsx
import { createContext, useContext, useState, useEffect } from "react";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    const storedTenant = localStorage.getItem("tenant");

    if (token) {
      if (storedTenant) {
        setTenant(JSON.parse(storedTenant));
      }
      fetchProfile().finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const fetchProfile = async () => {
    try {
      const response = await fetch("http://localhost:8000/auth/profile", {
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`
        }
      });

      if (response.ok) {
        const tenantData = await response.json();
        setTenant(tenantData);
        localStorage.setItem("tenant", JSON.stringify(tenantData));
      } else if (response.status === 401) {
        await refreshToken();
        await fetchProfile();
      }
    } catch (error) {
      console.error("Failed to fetch profile:", error);
    }
  };

  const login = async (email, password) => {
    const response = await fetch("http://localhost:8000/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }

    const data = await response.json();
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    localStorage.setItem("tenant", JSON.stringify(data.tenant));
    setTenant(data.tenant);
  };

  const logout = async () => {
    try {
      await fetch("http://localhost:8000/auth/logout", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`
        }
      });
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("tenant");
      setTenant(null);
    }
  };

  const refreshToken = async () => {
    const response = await fetch("http://localhost:8000/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        refresh_token: localStorage.getItem("refresh_token")
      })
    });

    if (!response.ok) {
      logout();
      throw new Error("Session expired");
    }

    const tokens = await response.json();
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
  };

  return (
    <AuthContext.Provider value={{ tenant, login, logout, loading, refreshToken }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
```

### Protected Route

```javascript
// ProtectedRoute.jsx
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export const ProtectedRoute = ({ children }) => {
  const { tenant, loading } = useAuth();

  if (loading) {
    return <div>Loading...</div>;
  }

  return tenant ? children : <Navigate to="/login" />;
};
```

---

## Vue Integration Example

### Pinia Store (Tenant-Based)

```javascript
// stores/auth.js
import { defineStore } from "pinia";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    tenant: null,
    accessToken: localStorage.getItem("access_token"),
    refreshToken: localStorage.getItem("refresh_token")
  }),

  actions: {
    async login(email, password) {
      const response = await fetch("http://localhost:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail);
      }

      const data = await response.json();
      this.accessToken = data.access_token;
      this.refreshToken = data.refresh_token;
      this.tenant = data.tenant;
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      localStorage.setItem("tenant", JSON.stringify(data.tenant));
    },

    async fetchProfile() {
      const response = await fetch("http://localhost:8000/auth/profile", {
        headers: this.authHeader
      });

      if (response.ok) {
        this.tenant = await response.json();
        localStorage.setItem("tenant", JSON.stringify(this.tenant));
      } else if (response.status === 401) {
        await this.refreshToken();
        await this.fetchProfile();
      }
    },

    async refreshToken() {
      const response = await fetch("http://localhost:8000/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: this.refreshToken })
      });

      if (!response.ok) {
        this.logout();
        throw new Error("Session expired");
      }

      const tokens = await response.json();
      this.accessToken = tokens.access_token;
      this.refreshToken = tokens.refresh_token;
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
    },

    async logout() {
      try {
        await fetch("http://localhost:8000/auth/logout", {
          method: "POST",
          headers: this.authHeader
        });
      } finally {
        this.tenant = null;
        this.accessToken = null;
        this.refreshToken = null;
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("tenant");
      }
    }
  },

  getters: {
    authHeader: (state) => ({
      "Authorization": `Bearer ${state.accessToken}`
    }),
    isAuthenticated: (state) => !!state.accessToken
  }
});
```

### Navigation Guard

```javascript
// router/index.js
import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = createRouter({
  routes: [
    // ... routes
  ]
});

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next("/login");
  } else if (to.meta.requiresAuth && !authStore.tenant) {
    try {
      await authStore.fetchProfile();
      next();
    } catch {
      next("/login");
    }
  } else {
    next();
  }
});

export default router;
```

---

## Axios Interceptor (Generic)

```javascript
// api.js
import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000"
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem("refresh_token");

      if (refreshToken) {
        try {
          const response = await axios.post(
            "http://localhost:8000/auth/refresh",
            { refresh_token: refreshToken }
          );

          localStorage.setItem("access_token", response.data.access_token);
          localStorage.setItem("refresh_token", response.data.refresh_token);

          // Retry original request
          error.config.headers.Authorization = `Bearer ${response.data.access_token}`;
          return axios(error.config);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("tenant");
          window.location.href = "/login";
        }
      } else {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default api;
```

---

## Wiki Integration

### Ingest Source (Add to Knowledge Base)

```javascript
const ingestSource = async (title, content, sourceType, tags) => {
  const response = await fetch("http://localhost:8000/wiki/ingest", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      title,
      content,
      source_type: sourceType,
      tags,
      generate_summary: true,
      create_entity_pages: true
    })
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
};
```

### Query Wiki (Ask Questions)

```javascript
const queryWiki = async (question, context) => {
  const response = await fetch("http://localhost:8000/wiki/query", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      question,
      context,
      max_pages: 5
    })
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json(); // { answer, citations, related_pages }
};
```

### Search Pages

```javascript
const searchPages = async (query) => {
  const response = await fetch(
    `http://localhost:8000/wiki/pages/search?q=${encodeURIComponent(query)}`,
    { headers: getAuthHeaders() }
  );

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
};
```

---

## Agent Configuration Integration

### Get Agent Status

```javascript
const getAgentStatus = async () => {
  const response = await fetch("http://localhost:8000/agent/status", {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: { is_configured, has_system_prompt, has_personality_prompt, config_id }
};
```

### Create/Update Agent Configuration

```javascript
const saveAgentConfig = async (systemPrompt, personalityPrompt) => {
  const response = await fetch("http://localhost:8000/agent/config", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      system_prompt: systemPrompt,
      personality_prompt: personalityPrompt
    })
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
};
```

### Partially Update Configuration

```javascript
const updateSystemPrompt = async (newSystemPrompt) => {
  const response = await fetch("http://localhost:8000/agent/config", {
    method: "PATCH",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      system_prompt: newSystemPrompt
    })
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
};
```

### Test Agent

```javascript
const testAgent = async (question, context) => {
  const response = await fetch("http://localhost:8000/agent/test", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      question,
      context
    })
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: { answer, sources, agent_config_used, wiki_context, web_search_used }
};
```

### Delete Agent Configuration

```javascript
const deleteAgentConfig = async () => {
  const response = await fetch("http://localhost:8000/agent/config", {
    method: "DELETE",
    headers: getAuthHeaders()
  });

  if (!response.ok && response.status !== 204) {
    throw new Error((await response.json()).detail);
  }

  return true;
};
```

---

## Booking System Integration (External API)

### List All Guests

```javascript
const listGuests = async (statusFilter) => {
  const url = statusFilter
    ? `http://localhost:8000/booking/guests?status=${statusFilter}`
    : "http://localhost:8000/booking/guests";

  const response = await fetch(url, { headers: getAuthHeaders() });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json(); // { guests: [...], total: 45 }
};
```

### Get Today's Bookings

```javascript
const getTodayBookings = async () => {
  const response = await fetch("http://localhost:8000/booking/guests/today", {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json(); // { bookings: [...], total: 5 }
};
```

### Get Guest Journey

```javascript
const getGuestJourney = async (guestId) => {
  const response = await fetch(
    `http://localhost:8000/booking/guests/${guestId}/journey`,
    { headers: getAuthHeaders() }
  );

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: {
  //   guest_name, room, check_in, check_out, status,
  //   milestones: [{ name, completed, time?, scheduled? }]
  // }
};
```

### Get Booking Statistics

```javascript
const getBookingStats = async () => {
  const response = await fetch("http://localhost:8000/booking/stats", {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: {
  //   total_active, arrived, confirmed, stayover, due_in,
  //   today_checkins, today_checkouts
  // }
};
```

---

## Journey Module Integration (Guest Messaging)

### Get Journey Configuration

```javascript
const getJourneyConfig = async () => {
  const response = await fetch("http://localhost:8000/journey/config", {
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: {
  //   id, tenant_id, is_enabled, hotel_city,
  //   morning_message_hour, breakfast_hour, lunch_hour, dinner_hour, evening_hour,
  //   enable_weather_based, enable_meal_reminders, enable_status_messages,
  //   include_due_in, include_arrived, include_stayover, include_checkout_today
  // }
};
```

### Update Journey Configuration

```javascript
const updateJourneyConfig = async (updates) => {
  const response = await fetch("http://localhost:8000/journey/config", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(updates)
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
};

// Example: Update city and enable weather-based messages
updateJourneyConfig({
  hotel_city: "Karachi",
  enable_weather_based: true
});
```

### Enable/Disable Journey Module

```javascript
const enableJourney = async () => {
  const response = await fetch("http://localhost:8000/journey/config/enable", {
    method: "POST",
    headers: getAuthHeaders()
  });
  return response.json();
};

const disableJourney = async () => {
  const response = await fetch("http://localhost:8000/journey/config/disable", {
    method: "POST",
    headers: getAuthHeaders()
  });
  return response.json();
};
```

### Get Current Weather

```javascript
const getWeather = async (city) => {
  const response = await fetch(
    `http://localhost:8000/journey/weather?city=${encodeURIComponent(city)}`,
    { headers: getAuthHeaders() }
  );

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: { status, temperature, condition, description, city }
};

// Get weather by coordinates
const getWeatherByCoords = async (lat, lon) => {
  const response = await fetch(
    `http://localhost:8000/journey/weather?lat=${lat}&lon=${lon}`,
    { headers: getAuthHeaders() }
  );

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
};
```

### List Active Guests

```javascript
const listJourneyGuests = async (statusFilter) => {
  const url = statusFilter
    ? `http://localhost:8000/journey/guests?status=${statusFilter}`
    : "http://localhost:8000/journey/guests";

  const response = await fetch(url, { headers: getAuthHeaders() });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: { guests: [{ id, gname, room, mobile, gstatus, cindate, coutdate }], total }
};

// Status filters: "DueIn", "Arrived", "StayOver", "Checkout"
listJourneyGuests("Arrived,StayOver");
```

### Send Message to Guest

```javascript
const sendGuestMessage = async (guestId, messageType) => {
  const response = await fetch("http://localhost:8000/journey/send", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      guest_id: guestId,
      message_type: messageType  // morning, lunch, dinner, welcome, etc.
    })
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: { status, message_id, sent_to }
};
```

### Broadcast Messages to All Guests

```javascript
const broadcastMessage = async (messageType) => {
  const response = await fetch(
    `http://localhost:8000/journey/send/broadcast?message_type=${messageType}`,
    {
      method: "POST",
      headers: getAuthHeaders()
    }
  );

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: {
  //   timestamp, message_type, weather,
  //   guests_count, messages_sent, errors
  // }
};

// Broadcast different message types
broadcastMessage("morning");   // 8 AM - Weather + activities
broadcastMessage("breakfast"); // 7 AM - Breakfast reminder
broadcastMessage("lunch");     // 11 AM - Lunch announcement
broadcastMessage("dinner");    // 6 PM - Dinner invitation
broadcastMessage("evening");   // 8 PM - Evening activities
```

### Send Welcome Message

```javascript
const sendWelcome = async (guestId) => {
  const response = await fetch(
    `http://localhost:8000/journey/send/welcome/${guestId}`,
    {
      method: "POST",
      headers: getAuthHeaders()
    }
  );

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: { message, status }
};
```

### Send Due-In Message (Pre-Arrival)

```javascript
const sendDueInMessages = async () => {
  const response = await fetch("http://localhost:8000/journey/send/due-in", {
    method: "POST",
    headers: getAuthHeaders()
  });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: { timestamp, guests_count, messages_sent, errors }
};
```

### Get Message Logs

```javascript
const getMessageLogs = async (limit = 50, offset = 0, messageType) => {
  let url = `http://localhost:8000/journey/logs?limit=${limit}&offset=${offset}`;
  if (messageType) {
    url += `&message_type=${messageType}`;
  }

  const response = await fetch(url, { headers: getAuthHeaders() });

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: { logs: [{ id, guest_name, room_number, message_type,
  //                    direction, content, sent_at, delivered }], total, limit, offset }
};
```

### AI Conversation with Guest

```javascript
const sendGuestConversation = async (mobile, message, tenantId) => {
  const response = await fetch(
    `http://localhost:8000/journey/conversation?tenant_id=${tenantId}&mobile=${encodeURIComponent(mobile)}&message=${encodeURIComponent(message)}`,
    {
      method: "POST",
      headers: getAuthHeaders()
    }
  );

  if (!response.ok) {
    throw new Error((await response.json()).detail);
  }

  return response.json();
  // Returns: { response, guest_name, room, wiki_context }
};
```

### Journey Dashboard Example (React)

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
    loadData();
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div className="journey-dashboard">
      <h2>Journey Messaging</h2>

      <div className="status-card">
        <h3>Current Status</h3>
        <p>Enabled: {config?.is_enabled ? 'Yes' : 'No'}</p>
        <p>Active Guests: {guests.length}</p>
        {weather?.status === 'ok' && (
          <p>Weather: {weather.temperature}C, {weather.condition}</p>
        )}
        <button onClick={() => toggleJourney(!config?.is_enabled)}>
          {config?.is_enabled ? 'Disable' : 'Enable'} Journey
        </button>
      </div>

      <div className="quick-actions">
        <h3>Send Messages</h3>
        <button onClick={() => broadcastMessage('morning')}>Morning</button>
        <button onClick={() => broadcastMessage('lunch')}>Lunch</button>
        <button onClick={() => broadcastMessage('dinner')}>Dinner</button>
        <button onClick={() => broadcastMessage('evening')}>Evening</button>
      </div>

      <div className="guest-section">
        <h3>Active Guests ({guests.length})</h3>
        <table>
          <thead>
            <tr><th>Name</th><th>Room</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {guests.map(guest => (
              <tr key={guest.id}>
                <td>{guest.gname}</td>
                <td>{guest.room}</td>
                <td>{guest.gstatus}</td>
                <td>
                  <button onClick={() => sendWelcome(guest.id)}>Welcome</button>
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

---

## Error Handling

### Common Error Responses

| Status | Error | Solution |
|--------|-------|----------|
| 400 | Email already registered | Tenant already exists |
| 401 | Invalid email or password | Check credentials |
| 401 | Invalid or expired token | Refresh token or login again |
| 401 | Token expired | Refresh access token |
| 404 | Not found | Check resource ID |
| 422 | Validation error | Check request body format |

### Example Error Handling

```javascript
const apiCall = async () => {
  try {
    const response = await fetch("http://localhost:8000/wiki/ingest", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ title: "Test", content: "Content" })
    });

    if (!response.ok) {
      const error = await response.json();

      switch (response.status) {
        case 400:
          console.error("Bad request:", error.detail);
          break;
        case 401:
          await refreshToken();
          return apiCall(); // Retry
        case 404:
          console.error("Not found:", error.detail);
          break;
        default:
          console.error("Server error:", error.detail);
      }
      return;
    }

    return await response.json();
  } catch (err) {
    console.error("Network error:", err);
  }
};
```

---

## Security Notes

1. **Never store tokens in localStorage for sensitive apps** - Consider httpOnly cookies
2. **Always use HTTPS in production** - Never send tokens over plain HTTP
3. **Implement token refresh before expiry** - Refresh 5 minutes before expiration
4. **Clear tokens on logout** - Ensure complete token cleanup
5. **Validate all inputs** - Always validate on server AND client
6. **Rate limiting** - Implement rate limiting on auth endpoints
7. **CORS** - Configure allowed origins properly in production
8. **API Keys are Shared** - OpenRouter/Tavily keys are shared, not per-tenant

---

## Production Checklist

- [ ] Use HTTPS
- [ ] Set strong SECRET_KEY (min 32 characters)
- [ ] Configure CORS_ORIGINS for your domain
- [ ] Set DEBUG=false in production
- [ ] Use connection pooling
- [ ] Set up rate limiting
- [ ] Implement logging/monitoring
- [ ] Set up database backups
- [ ] Configure token expiration appropriately
- [ ] Use secure password requirements
- [ ] Configure shared API keys (OPENROUTER_API_KEY, TAVILY_API_KEY)

---

## Multi-Tenant Data Isolation

Each tenant's data is isolated by `tenant_id`. When making API calls:

1. All authenticated requests include JWT with `tenant_id`
2. Wiki sources, pages, logs are all tenant-scoped
3. Tenant A cannot see or modify Tenant B's data

Example API call structure:
```
POST /wiki/ingest
Authorization: Bearer <tenant-A-token>  → tenant_id: "A"
                            ↓
                  Filtered by tenant_id
                            ↓
                  Only Tenant A's data
```

---

## Environment Variables (Frontend)

```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// API keys are configured on the SERVER, not in frontend
// Shared keys: OPENROUTER_API_KEY, TAVILY_API_KEY
```