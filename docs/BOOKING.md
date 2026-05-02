# Booking API - External Integration

Guide for integrating with the external booking system via Inika API.

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Endpoints](#endpoints)
4. [Frontend Integration](#frontend-integration)
5. [Guest Status Types](#guest-status-types)

---

## Overview

| Item | Value |
|------|-------|
| Base URL | `http://localhost:8000` |
| Auth Required | Yes (JWT Bearer token) |
| API Prefix | `/booking` |
| External API | `https://grssl.payfiller.com/inika/webhook` |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `INIKA_API_KEY` | External API authentication key |
| `INIKA_BOOKING_KEY` | Booking data access key |

---

## Authentication

All booking endpoints require JWT authentication:

```
Authorization: Bearer <access_token>
```

Token is obtained from `/auth/login` or `/auth/register`.

---

## Endpoints

### 1. Sync Guests from External API

Fetch guest inventory from external booking system and sync to local database.

**Endpoint**: `POST /booking/sync`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "status": "ok",
  "synced": 50,
  "total": 50
}
```

**Errors**:
- `500`: API fetch failed or data parsing error

---

### 2. Fetch Guests (Raw Data)

Fetch guest data from external API without syncing to local database.

**Endpoint**: `GET /booking/fetch`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "status": "ok",
  "data": "[...]"
}
```

---

### 3. List All Guests

Get all active guests, optionally filtered by status.

**Endpoint**: `GET /booking/guests`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| status | string | Filter by status (optional) |

**Example**: `GET /booking/guests?status=Arrived`

**Response** (200 OK):
```json
{
  "guests": [
    {
      "id": "booking-123",
      "tid": "tenant-123",
      "rid": "room-456",
      "room": "101",
      "gname": "John Doe",
      "mobile": "+1234567890",
      "gstatus": "Arrived",
      "gcount": "2",
      "btype": "Individual",
      "sub_booking_id": "SUB-001",
      "driver_tag": "",
      "cindate": "2024-01-15",
      "coutdate": "2024-01-18",
      "synced_at": 1705320000
    }
  ],
  "total": 1
}
```

---

### 4. Get Today's Bookings

Get today's check-ins and check-outs.

**Endpoint**: `GET /booking/guests/today`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "bookings": [...],
  "total": 5
}
```

---

### 5. Get Guest by ID

**Endpoint**: `GET /booking/guests/{guest_id}`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "id": "booking-123",
  "gname": "John Doe",
  "room": "101",
  "mobile": "+1234567890",
  "gstatus": "Arrived",
  "cindate": "2024-01-15",
  "coutdate": "2024-01-18"
}
```

---

### 6. Get Guest by Room

Get the current guest in a specific room.

**Endpoint**: `GET /booking/guests/room/{room}`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK): Returns guest object

**Errors**:
- `404`: No active guest in this room

---

### 7. Get Guest by Phone

Find guest by mobile number.

**Endpoint**: `GET /booking/guests/phone/{mobile}`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK): Returns guest object

**Errors**:
- `404`: Guest not found

---

### 8. Get Guest Journey

Get guest journey status with milestones.

**Endpoint**: `GET /booking/guests/{guest_id}/journey`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "guest_name": "John Doe",
  "room": "101",
  "check_in": "2024-01-15",
  "check_out": "2024-01-18",
  "status": "StayOver",
  "guests_count": "2",
  "booking_type": "Individual",
  "milestones": [
    {
      "name": "Checked In",
      "completed": true,
      "time": "2024-01-15 14:00"
    },
    {
      "name": "Welcome Message",
      "completed": true
    },
    {
      "name": "Check Out",
      "completed": false,
      "scheduled": "2024-01-18 11:00"
    }
  ]
}
```

---

### 9. Get Booking Statistics

**Endpoint**: `GET /booking/stats`

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "total_active": 45,
  "arrived": 10,
  "confirmed": 15,
  "stayover": 20,
  "due_in": 5,
  "today_checkins": 8,
  "today_checkouts": 3
}
```

---

## Frontend Integration

### React - Guest List Component

```jsx
import { useState, useEffect } from 'react';

export default function GuestList() {
  const [guests, setGuests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  });

  useEffect(() => {
    fetchGuests();
  }, [statusFilter]);

  const fetchGuests = async () => {
    try {
      const url = statusFilter
        ? `/booking/guests?status=${statusFilter}`
        : '/booking/guests';

      const response = await fetch(url, { headers: getAuthHeaders() });
      const data = await response.json();
      setGuests(data.guests);
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch guests:', err);
    }
  };

  const syncGuests = async () => {
    try {
      const response = await fetch('/booking/sync', {
        method: 'POST',
        headers: getAuthHeaders()
      });
      const result = await response.json();

      if (result.status === 'ok') {
        alert(`Synced ${result.synced} guests`);
        fetchGuests();
      }
    } catch (err) {
      alert('Sync failed: ' + err.message);
    }
  };

  if (loading) return <div>Loading guests...</div>;

  return (
    <div className="guest-list">
      <h2>Guest Management</h2>

      <div className="filters">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All Active</option>
          <option value="Arrived">Arrived</option>
          <option value="Confirmed">Confirmed</option>
          <option value="StayOver">Stay Over</option>
          <option value="Due In">Due In</option>
        </select>

        <button onClick={syncGuests}>Sync from Booking System</button>
      </div>

      <table>
        <thead>
          <tr>
            <th>Room</th>
            <th>Name</th>
            <th>Phone</th>
            <th>Status</th>
            <th>Check-in</th>
            <th>Check-out</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {guests.map((guest) => (
            <tr key={guest.id}>
              <td>{guest.room}</td>
              <td>{guest.gname}</td>
              <td>{guest.mobile}</td>
              <td>
                <span className={`status ${guest.gstatus.toLowerCase()}`}>
                  {guest.gstatus}
                </span>
              </td>
              <td>{guest.cindate}</td>
              <td>{guest.coutdate}</td>
              <td>
                <button
                  onClick={() => window.location.href = `/guests/${guest.id}`}
                >
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### React - Guest Lookup

```jsx
import { useState } from 'react';

export default function GuestLookup() {
  const [searchType, setSearchType] = useState('mobile');
  const [searchValue, setSearchValue] = useState('');
  const [guest, setGuest] = useState(null);
  const [error, setError] = useState(null);

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  });

  const lookupGuest = async () => {
    if (!searchValue) return;

    try {
      const endpoint = searchType === 'mobile'
        ? `/booking/guests/phone/${searchValue}`
        : `/booking/guests/room/${searchValue}`;

      const response = await fetch(endpoint, { headers: getAuthHeaders() });

      if (response.status === 404) {
        setError('Guest not found');
        setGuest(null);
        return;
      }

      const data = await response.json();
      setGuest(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="guest-lookup">
      <h2>Find Guest</h2>

      <div className="search-form">
        <select
          value={searchType}
          onChange={(e) => setSearchType(e.target.value)}
        >
          <option value="mobile">By Phone Number</option>
          <option value="room">By Room Number</option>
        </select>

        <input
          type="text"
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          placeholder={
            searchType === 'mobile'
              ? 'Enter phone number'
              : 'Enter room number'
          }
        />

        <button onClick={lookupGuest}>Search</button>
      </div>

      {error && <div className="error">{error}</div>}

      {guest && (
        <div className="guest-details">
          <h3>{guest.gname}</h3>
          <p>Room: {guest.room}</p>
          <p>Phone: {guest.mobile}</p>
          <p>Status: {guest.gstatus}</p>
          <p>Check-in: {guest.cindate}</p>
          <p>Check-out: {guest.coutdate}</p>

          <button
            onClick={() => window.location.href = `/guests/${guest.id}/journey`}
          >
            View Journey
          </button>
        </div>
      )}
    </div>
  );
}
```

---

## Guest Status Types

| Status | Description |
|--------|-------------|
| `Due In` | Booking confirmed, guest hasn't arrived |
| `Confirmed` | Booking confirmed |
| `Arrived` | Guest has checked in |
| `StayOver` | Guest currently staying overnight |
| `CheckedOut` | Guest has checked out |

## Booking Types

| Type | Description |
|------|-------------|
| `Individual` | Single booking |
| `Group` | Group booking |
| `Corporate` | Corporate/business booking |
| (varies) | Other booking types may exist |

---

## Sync Workflow

```
1. Frontend calls POST /booking/sync
   ↓
2. Backend fetches from external API
   ↓
3. External API returns guest inventory
   ↓
4. Backend syncs to local database
   ↓
5. Returns synced count
   ↓
6. Frontend shows updated guest list
```

---

## Error Handling

| Status | Error | Solution |
|--------|-------|----------|
| 401 | Not authenticated | Login and include token |
| 404 | Guest not found | Check search parameters |
| 500 | API error | Check INIKA_BOOKING_KEY env var |