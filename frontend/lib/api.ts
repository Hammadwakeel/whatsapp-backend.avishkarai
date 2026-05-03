const DEFAULT_API = "http://localhost:8000";

export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (raw && raw.length > 0) {
    return raw.replace(/\/$/, "");
  }
  return DEFAULT_API;
}

// =============================================================================
// Types
// =============================================================================

export type Tenant = {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  hotel_name: string | null;
  hotel_address: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  tenant: Tenant;
};

export type ProfileResponse = Tenant;

export type PasswordChangeRequest = {
  current_password: string;
  new_password: string;
};

// =============================================================================
// Storage Keys
// =============================================================================

const ACCESS_TOKEN_KEY = "inika_access_token";
const REFRESH_TOKEN_KEY = "inika_refresh_token";
const TENANT_KEY = "inika_tenant";

// =============================================================================
// Token Management
// =============================================================================

export function getStoredToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(ACCESS_TOKEN_KEY) || "";
}

export function getStoredRefreshToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(REFRESH_TOKEN_KEY) || "";
}

export function getStoredTenant(): Tenant | null {
  if (typeof window === "undefined") return null;
  const data = window.localStorage.getItem(TENANT_KEY);
  if (!data) return null;
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}

export function setStoredAuth(accessToken: string, refreshToken: string, tenant: Tenant) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  window.localStorage.setItem(TENANT_KEY, JSON.stringify(tenant));
}

export function clearStoredAuth() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  window.localStorage.removeItem(TENANT_KEY);
}

// =============================================================================
// Headers
// =============================================================================

export function jsonAuthHeaders(): Record<string, string> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export function bearerAuthHeaders(): Record<string, string> {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// =============================================================================
// Auth API
// =============================================================================

export const authAPI = {
  async register(data: {
    name: string;
    email: string;
    password: string;
    phone?: string;
    hotel_name?: string;
    hotel_address?: string;
  }): Promise<AuthResponse> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Registration failed" }));
      throw new Error(error.detail || "Registration failed");
    }

    return response.json();
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(error.detail || "Invalid email or password");
    }

    return response.json();
  },

  async refresh(): Promise<AuthResponse> {
    const base = getApiBaseUrl();
    const refreshToken = getStoredRefreshToken();

    if (!refreshToken) {
      throw new Error("No refresh token");
    }

    const response = await fetch(`${base}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      clearStoredAuth();
      throw new Error("Session expired");
    }

    return response.json();
  },

  async logout(): Promise<void> {
    const base = getApiBaseUrl();
    try {
      await fetch(`${base}/auth/logout`, {
        method: "POST",
        headers: jsonAuthHeaders(),
      });
    } catch {
      // Ignore network errors
    }
    clearStoredAuth();
  },

  async logoutAll(): Promise<{ message: string }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/auth/logout-all`, {
      method: "POST",
      headers: jsonAuthHeaders(),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Logout failed" }));
      throw new Error(error.detail || "Logout failed");
    }

    clearStoredAuth();
    return response.json();
  },
};

// =============================================================================
// Profile API
// =============================================================================

export const profileAPI = {
  async getProfile(): Promise<ProfileResponse> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/auth/profile`, {
      headers: jsonAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error("Unauthorized");
    }

    return response.json();
  },

  async updateProfile(data: Partial<{
    name: string;
    phone: string;
    hotel_address: string;
  }>): Promise<ProfileResponse> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/auth/profile`, {
      method: "PATCH",
      headers: jsonAuthHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Update failed" }));
      throw new Error(error.detail || "Update failed");
    }

    return response.json();
  },

  async changePassword(current_password: string, new_password: string): Promise<void> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/auth/change-password`, {
      method: "POST",
      headers: jsonAuthHeaders(),
      body: JSON.stringify({ current_password, new_password }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Password change failed" }));
      throw new Error(error.detail || "Password change failed");
    }
  },
};

// =============================================================================
// Convenience exports
// =============================================================================

export async function logout(): Promise<void> {
  return authAPI.logout();
}

// =============================================================================
// Wiki / Knowledge API
// =============================================================================

export type WikiSource = {
  id: string;
  title: string;
  source_type: string;
  summary?: string;
  tags: string[];
  is_processed: boolean;
  created_at: string;
};

export type WikiPage = {
  id: string;
  title: string;
  slug: string;
  content: string;
  page_type: string;
  summary?: string;
  tags: string[];
  is_draft: boolean;
  created_at: string;
  updated_at: string;
};

export const wikiAPI = {
  async getIndex(): Promise<{ total_pages: number; total_sources: number; categories: Record<string, number> }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/wiki/index`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get wiki index");
    return response.json();
  },

  async getSources(): Promise<{ sources: WikiSource[]; total: number }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/wiki/sources`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get sources");
    return response.json();
  },

  async getPages(): Promise<{ pages: WikiPage[]; total: number }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/wiki/pages`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get pages");
    return response.json();
  },

  async searchPages(query: string): Promise<{ pages: WikiPage[]; total: number }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/wiki/pages/search?q=${encodeURIComponent(query)}`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to search pages");
    return response.json();
  },

  async ingest(title: string, content: string, sourceType: string, tags: string[]): Promise<{
    source: WikiSource;
    created_pages: WikiPage[];
    updated_pages: WikiPage[];
  }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/wiki/ingest`, {
      method: "POST",
      headers: jsonAuthHeaders(),
      body: JSON.stringify({
        title,
        content,
        source_type: sourceType,
        tags,
        generate_summary: true,
        create_entity_pages: true,
        update_related_pages: true,
      }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Ingest failed" }));
      throw new Error(error.detail || "Ingest failed");
    }
    return response.json();
  },

  async query(question: string, context?: string): Promise<{ answer: string; citations: { page_title: string; excerpt: string }[] }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/wiki/query`, {
      method: "POST",
      headers: jsonAuthHeaders(),
      body: JSON.stringify({ question, context }),
    });
    if (!response.ok) throw new Error("Failed to query wiki");
    return response.json();
  },
};

// =============================================================================
// Agent API
// =============================================================================

export type AgentConfig = {
  id: string;
  system_prompt: string | null;
  personality_prompt: string | null;
  updated_at: string;
};

export const agentAPI = {
  async getStatus(): Promise<{ is_configured: boolean; has_system_prompt: boolean; has_personality_prompt: boolean }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/agent/status`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get agent status");
    return response.json();
  },

  async getConfig(): Promise<AgentConfig | null> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/agent/config`, {
      headers: jsonAuthHeaders(),
    });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error("Failed to get agent config");
    return response.json();
  },

  async saveConfig(systemPrompt: string, personalityPrompt: string): Promise<AgentConfig> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/agent/config`, {
      method: "POST",
      headers: jsonAuthHeaders(),
      body: JSON.stringify({ system_prompt: systemPrompt, personality_prompt: personalityPrompt }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Failed to save config" }));
      throw new Error(error.detail || "Failed to save config");
    }
    return response.json();
  },

  async updateConfig(data: Partial<{ system_prompt: string; personality_prompt: string }>): Promise<AgentConfig> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/agent/config`, {
      method: "PATCH",
      headers: jsonAuthHeaders(),
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error("Failed to update config");
    return response.json();
  },

  async deleteConfig(): Promise<void> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/agent/config`, {
      method: "DELETE",
      headers: jsonAuthHeaders(),
    });
    if (!response.ok && response.status !== 204) throw new Error("Failed to delete config");
  },

  async test(question: string, context?: string): Promise<{ answer: string; sources: string[] }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/agent/test`, {
      method: "POST",
      headers: jsonAuthHeaders(),
      body: JSON.stringify({ question, context }),
    });
    if (!response.ok) throw new Error("Failed to test agent");
    return response.json();
  },
};

// =============================================================================
// WhatsApp API
// =============================================================================

export type WhatsAppSession = {
  id: string;
  tenant_id?: string;
  status: string;
  phone_number?: string | null;
  display_name?: string | null;
  qr_code?: string | null;
  connected_at?: string | null;
};

export type WhatsAppMessageRecord = {
  id: string;
  tenant_id?: string;
  direction: string;
  from_number: string;
  to_number: string | null;
  content: string;
  created_at: string;
  agent_response?: string | null;
  wiki_sources?: { sources?: string[] } | Record<string, unknown> | null;
  web_search_used: boolean;
};

export const whatsappAPI = {
  async getSession(): Promise<WhatsAppSession | null> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/whatsapp/session`, {
      headers: jsonAuthHeaders(),
    });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error("Failed to get session");
    return response.json();
  },

  async getStatus(): Promise<{
    status: string;
    qrcode?: string;
    is_connected?: boolean;
    connected?: boolean;
    local_session_id?: string | null;
    pairing_code?: string | null;
    evolution_detail?: string | null;
  }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/whatsapp/status`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get status");
    return response.json();
  },

  async connect(): Promise<{
    status: string;
    qr_code?: string;
    connected?: boolean;
    local_session_id?: string;
    message?: string;
    evolution_url?: string;
    instance_name?: string;
    evolution_detail?: string | null;
  }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/whatsapp/connect`, {
      method: "POST",
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to connect WhatsApp");
    return response.json();
  },

  async disconnect(): Promise<void> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/whatsapp/disconnect`, {
      method: "POST",
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to disconnect");
  },

  async resetSession(): Promise<{
    status: string;
    qr_code?: string;
    message?: string;
    evolution_detail?: string | null;
  }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/whatsapp/reset-session`, {
      method: "GET",
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to reset session");
    return response.json();
  },

  async getQRCode(): Promise<{ qrcode: string } | null> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/whatsapp/qrcode`, {
      headers: jsonAuthHeaders(),
    });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error("Failed to get QR code");
    return response.json();
  },

  async sendMessage(to: string, message: string): Promise<{ message_id?: string | null; status: string }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/whatsapp/send`, {
      method: "POST",
      headers: jsonAuthHeaders(),
      body: JSON.stringify({ to, message }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Failed to send" }));
      throw new Error(error.detail || "Failed to send message");
    }
    return response.json();
  },

  async getMessages(
    pageSize: number = 100,
    order: "asc" | "desc" = "desc",
    page: number = 1,
  ): Promise<{ messages: WhatsAppMessageRecord[]; total: number; page: number; page_size: number }> {
    const base = getApiBaseUrl();
    const response = await fetch(
      `${base}/whatsapp/messages?page=${page}&page_size=${pageSize}&order=${order}`,
      {
        headers: jsonAuthHeaders(),
      },
    );
    if (!response.ok) throw new Error("Failed to get messages");
    return response.json();
  },

  /**
   * Connect to Server-Sent Events for real-time WhatsApp updates.
   * Returns an EventSource that emits:
   * - `connected`: Initial connection event
   * - `whatsapp_status`: Connection status changes
   * - `new_message`: New inbound/outbound messages
   * - `connection_state`: CONNECTED/DISCONNECTED state changes
   * - `session_disconnected`: When session unexpectedly disconnects
   */
  connectSSE(onMessage?: (type: string, data: Record<string, unknown>) => void): EventSource {
    const base = getApiBaseUrl();
    const token = getStoredToken();
    // Pass token as query param since EventSource doesn't support custom headers
    const url = `${base}/whatsapp/events${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    const eventSource = new EventSource(url);

    if (onMessage) {
      eventSource.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          onMessage(parsed.type || "message", parsed.data || {});
        } catch {
          onMessage("message", { raw: event.data });
        }
      };
    }

    return eventSource;
  },
};

// =============================================================================
// Booking API
// =============================================================================

export type BookingGuest = {
  id: string;
  gname: string;
  room: string;
  mobile: string;
  gstatus: string;
  cindate: string;
  coutdate: string;
};

export type BookingStats = {
  total_active: number;
  arrived: number;
  confirmed: number;
  stayover: number;
  due_in: number;
  today_checkins: number;
  today_checkouts: number;
};

export const bookingAPI = {
  async sync(): Promise<{ status: string; synced: number; total: number }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/booking/sync`, {
      method: "POST",
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to sync");
    return response.json();
  },

  async getGuests(status?: string): Promise<{ guests: BookingGuest[]; total: number }> {
    const base = getApiBaseUrl();
    const url = status ? `${base}/booking/guests?status=${status}` : `${base}/booking/guests`;
    const response = await fetch(url, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get guests");
    return response.json();
  },

  async getTodayBookings(): Promise<{ bookings: BookingGuest[]; total: number }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/booking/guests/today`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get today's bookings");
    return response.json();
  },

  async getStats(): Promise<BookingStats> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/booking/stats`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get stats");
    return response.json();
  },

  async getGuestJourney(guestId: string): Promise<{ milestones: Array<{ name: string; completed: boolean; time?: string }> }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/booking/guests/${guestId}/journey`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get guest journey");
    return response.json();
  },
};

// =============================================================================
// Journey API
// =============================================================================

export type JourneyConfig = {
  id: string;
  tenant_id: string;
  is_enabled: boolean;
  hotel_city: string | null;
  hotel_latitude?: string | null;
  hotel_longitude?: string | null;
  morning_message_hour: number;
  breakfast_hour: number;
  lunch_hour: number;
  dinner_hour: number;
  evening_hour: number;
  enable_weather_based: boolean;
  enable_meal_reminders: boolean;
  enable_status_messages: boolean;
  enable_conversation?: boolean;
  max_messages_per_day?: number;
  include_due_in: boolean;
  include_arrived: boolean;
  include_stayover: boolean;
  include_checkout_today: boolean;
};

export const journeyAPI = {
  async getConfig(): Promise<JourneyConfig> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/journey/config`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get config");
    return response.json();
  },

  async updateConfig(data: Partial<JourneyConfig>): Promise<JourneyConfig> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/journey/config`, {
      method: "POST",
      headers: jsonAuthHeaders(),
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error("Failed to update config");
    return response.json();
  },

  async enable(): Promise<void> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/journey/config/enable`, {
      method: "POST",
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to enable");
  },

  async disable(): Promise<void> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/journey/config/disable`, {
      method: "POST",
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to disable");
  },

  async getWeather(city?: string, lat?: number, lon?: number): Promise<{ status: string; temperature: number; condition: string; description: string; city: string }> {
    const base = getApiBaseUrl();
    let url = `${base}/journey/weather`;
    if (city) url += `?city=${encodeURIComponent(city)}`;
    else if (lat !== undefined && lon !== undefined) url += `?lat=${lat}&lon=${lon}`;
    const response = await fetch(url, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get weather");
    return response.json();
  },

  async getGuests(status?: string): Promise<{ guests: BookingGuest[]; total: number }> {
    const base = getApiBaseUrl();
    const url = status ? `${base}/journey/guests?status=${status}` : `${base}/journey/guests`;
    const response = await fetch(url, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get guests");
    return response.json();
  },

  async getLogs(limit: number = 50, offset: number = 0, messageType?: string): Promise<{ logs: Array<{ id: string; guest_name: string; message_type: string; content: string; sent_at: string }>; total: number }> {
    const base = getApiBaseUrl();
    let url = `${base}/journey/logs?limit=${limit}&offset=${offset}`;
    if (messageType) url += `&message_type=${messageType}`;
    const response = await fetch(url, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get logs");
    return response.json();
  },

  async sendMessage(guestId: string, messageType: string): Promise<{ status: string; message_id: string }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/journey/send`, {
      method: "POST",
      headers: jsonAuthHeaders(),
      body: JSON.stringify({ guest_id: guestId, message_type: messageType }),
    });
    if (!response.ok) throw new Error("Failed to send message");
    return response.json();
  },

  async broadcast(messageType: string): Promise<{ timestamp: string; guests_count: number; messages_sent: number; errors: string[] }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/journey/send/broadcast?message_type=${messageType}`, {
      method: "POST",
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to broadcast");
    return response.json();
  },

  async getSchedulerStatus(): Promise<{
    scheduler_running: boolean;
    tenant_scheduled: boolean;
    jobs: Array<{ job_id: string; next_run: string | null; active: boolean }>;
  }> {
    const base = getApiBaseUrl();
    const response = await fetch(`${base}/journey/scheduler/status`, {
      headers: jsonAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to get scheduler status");
    return response.json();
  },
};