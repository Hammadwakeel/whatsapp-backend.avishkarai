"use client";

import { useEffect, useState } from "react";
import { MapPin, MessageSquare, Sun, Coffee, UtensilsCrossed, Moon, Send, RefreshCw, Loader2, Check, X, Cloud, CloudRain, Thermometer } from "lucide-react";
import { journeyAPI, JourneyConfig, BookingGuest } from "@/lib/api";
import NavigationWrapper from "@/components/NavigationWrapper";

export default function JourneyPage() {
  return (
    <NavigationWrapper>
      <JourneyContent />
    </NavigationWrapper>
  );
}

function JourneyContent() {
  const [config, setConfig] = useState<JourneyConfig | null>(null);
  const [guests, setGuests] = useState<BookingGuest[]>([]);
  const [logs, setLogs] = useState<Array<{ id: string; guest_name: string; message_type: string; content: string; sent_at: string }>>([]);
  const [weather, setWeather] = useState<{ status: string; temperature: number; condition: string; city: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [broadcasting, setBroadcasting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [configData, guestsData, logsData] = await Promise.all([
        journeyAPI.getConfig().catch(() => null),
        journeyAPI.getGuests().catch(() => ({ guests: [], total: 0 })),
        journeyAPI.getLogs(10).catch(() => ({ logs: [], total: 0 })),
      ]);
      setConfig(configData);
      setGuests(guestsData.guests);
      setLogs(logsData.logs);

      // Get weather if config exists
      if (configData?.hotel_city) {
        try {
          const weatherData = await journeyAPI.getWeather(configData.hotel_city);
          setWeather(weatherData);
        } catch {
          // Weather is optional
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const toggleJourney = async () => {
    if (!config) return;
    try {
      if (config.is_enabled) {
        await journeyAPI.disable();
      } else {
        await journeyAPI.enable();
      }
      loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to toggle";
      setError(msg);
    }
  };

  const broadcastMessage = async (type: string) => {
    setBroadcasting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const result = await journeyAPI.broadcast(type);
      setSuccessMsg(`Sent ${result.messages_sent} ${type} messages to ${result.guests_count} guests`);
      loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Broadcast failed";
      setError(msg);
    } finally {
      setBroadcasting(false);
      setTimeout(() => setSuccessMsg(null), 4000);
    }
  };

  const getWeatherIcon = (condition: string) => {
    const lower = condition?.toLowerCase() || "";
    if (lower.includes("rain")) return <CloudRain className="h-5 w-5" />;
    if (lower.includes("cloud")) return <Cloud className="h-5 w-5" />;
    return <Sun className="h-5 w-5" />;
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-white px-6 py-12">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <header className="mb-10 border-y border-black bg-white px-6 py-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center border border-black bg-black text-white">
                <MapPin className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-3xl font-black tracking-tight uppercase">Journey Engine</h1>
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  AI-powered guest messaging system
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={loadData}
                className="flex items-center gap-2 border border-black px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] transition hover:bg-black hover:text-white"
              >
                <RefreshCw className="h-4 w-4" />
                Refresh
              </button>
            </div>
          </div>
        </header>

        {/* Error */}
        {error && (
          <div className="mb-6 border border-red-500 bg-red-50 px-4 py-3">
            <p className="font-mono text-xs text-red-600">ERROR: {error}</p>
          </div>
        )}

        {/* Success */}
        {successMsg && (
          <div className="mb-6 border border-green-500 bg-green-50 px-4 py-3">
            <p className="font-mono text-xs text-green-700">{successMsg}</p>
          </div>
        )}

        {/* Config & Status */}
        {loading ? (
          <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-32 animate-pulse bg-zinc-100" />
            ))}
          </div>
        ) : (
          <>
            {/* Journey Status Card */}
            <div className="mb-8 border border-black">
              <div className="flex items-center justify-between border-b border-black bg-black px-6 py-4">
                <span className="font-mono text-sm font-semibold uppercase text-white tracking-wider">
                  Journey Configuration
                </span>
                <button
                  onClick={toggleJourney}
                  className={`flex items-center gap-2 border px-4 py-2 text-[10px] font-black uppercase tracking-wider transition ${
                    config?.is_enabled
                      ? "border-green-500 text-green-500 hover:bg-green-500 hover:text-white"
                      : "border-zinc-400 text-zinc-400 hover:bg-zinc-400 hover:text-white"
                  }`}
                >
                  {config?.is_enabled ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
                  {config?.is_enabled ? "Enabled" : "Disabled"}
                </button>
              </div>
              <div className="grid grid-cols-1 gap-px bg-black md:grid-cols-4">
                <div className="bg-white p-4">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">City</p>
                  <p className="mt-1 font-mono text-lg font-bold">{config?.hotel_city || "Not set"}</p>
                </div>
                <div className="bg-white p-4">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Weather</p>
                  {weather?.status === "ok" ? (
                    <div className="mt-1 flex items-center gap-2">
                      {getWeatherIcon(weather.condition)}
                      <span className="font-mono text-lg font-bold">{weather.temperature}°C</span>
                      <span className="font-mono text-xs text-zinc-500">{weather.condition}</span>
                    </div>
                  ) : (
                    <p className="font-mono text-lg font-bold text-zinc-400">N/A</p>
                  )}
                </div>
                <div className="bg-white p-4">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Active Guests</p>
                  <p className="mt-1 font-mono text-lg font-bold">{guests.length}</p>
                </div>
                <div className="bg-white p-4">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Message Types</p>
                  <p className="mt-1 font-mono text-xs">
                    {config?.enable_meal_reminders ? "Meal " : ""}
                    {config?.enable_weather_based ? "Weather " : ""}
                    {config?.enable_status_messages ? "Status" : ""}
                  </p>
                </div>
              </div>
            </div>

            {/* Broadcast Actions */}
            <div className="mb-8">
              <h2 className="mb-4 text-xs font-black uppercase tracking-widest text-zinc-500">
                Broadcast Messages
              </h2>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
                <BroadcastButton
                  icon={Sun}
                  label="Morning"
                  time="8:00 AM"
                  color="black"
                  onClick={() => broadcastMessage("morning")}
                  disabled={broadcasting}
                />
                <BroadcastButton
                  icon={Coffee}
                  label="Breakfast"
                  time="7:00 AM"
                  color="amber"
                  onClick={() => broadcastMessage("breakfast")}
                  disabled={broadcasting}
                />
                <BroadcastButton
                  icon={UtensilsCrossed}
                  label="Lunch"
                  time="11:00 AM"
                  color="blue"
                  onClick={() => broadcastMessage("lunch")}
                  disabled={broadcasting}
                />
                <BroadcastButton
                  icon={UtensilsCrossed}
                  label="Dinner"
                  time="6:00 PM"
                  color="purple"
                  onClick={() => broadcastMessage("dinner")}
                  disabled={broadcasting}
                />
                <BroadcastButton
                  icon={Moon}
                  label="Evening"
                  time="8:00 PM"
                  color="zinc"
                  onClick={() => broadcastMessage("evening")}
                  disabled={broadcasting}
                />
              </div>
            </div>

            {/* Guest List & Logs */}
            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              {/* Active Guests */}
              <div className="border border-black">
                <div className="border-b border-black bg-black px-4 py-3">
                  <h3 className="font-mono text-xs font-semibold uppercase text-white tracking-wider">
                    Active Guests ({guests.length})
                  </h3>
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {guests.length === 0 ? (
                    <div className="p-6 text-center">
                      <p className="font-mono text-sm text-zinc-500">No active guests</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-gray-100">
                      {guests.slice(0, 10).map((guest, i) => (
                        <div key={i} className="flex items-center justify-between px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 items-center justify-center border border-black bg-gray-100 font-mono text-xs font-bold">
                              {guest.gname?.charAt(0) || "?"}
                            </div>
                            <div>
                              <p className="font-mono text-sm font-medium">{guest.gname}</p>
                              <p className="font-mono text-[10px] text-zinc-500">Room {guest.room}</p>
                            </div>
                          </div>
                          <span className={`badge ${guest.gstatus === "StayOver" || guest.gstatus === "Arrived" ? "badge-success" : "badge-info"}`}>
                            {guest.gstatus}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Recent Logs */}
              <div className="border border-black">
                <div className="border-b border-black bg-black px-4 py-3">
                  <h3 className="font-mono text-xs font-semibold uppercase text-white tracking-wider">
                    Recent Messages
                  </h3>
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {logs.length === 0 ? (
                    <div className="p-6 text-center">
                      <p className="font-mono text-sm text-zinc-500">No messages sent yet</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-gray-100">
                      {logs.map((log, i) => (
                        <div key={i} className="px-4 py-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono text-xs font-bold uppercase">{log.message_type}</span>
                            <span className="font-mono text-[10px] text-zinc-400">
                              {new Date(log.sent_at).toLocaleTimeString()}
                            </span>
                          </div>
                          <p className="font-mono text-sm text-zinc-700">{log.guest_name}</p>
                          <p className="mt-1 font-mono text-xs text-zinc-500 truncate">{log.content}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        {/* Footer */}
        <footer className="mt-16 border-t border-black bg-black px-6 py-8">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">
            <span>Journey Engine v1.0</span>
            <span>Inika Bot</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

function BroadcastButton({
  icon: Icon,
  label,
  time,
  color,
  onClick,
  disabled,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  time: string;
  color: string;
  onClick: () => void;
  disabled: boolean;
}) {
  const colorClasses: Record<string, string> = {
    black: "bg-black text-white border-black hover:bg-zinc-800",
    amber: "bg-amber-100 text-amber-800 border-amber-300 hover:bg-amber-200",
    blue: "bg-blue-100 text-blue-800 border-blue-300 hover:bg-blue-200",
    purple: "bg-purple-100 text-purple-800 border-purple-300 hover:bg-purple-200",
    zinc: "bg-zinc-100 text-zinc-700 border-zinc-300 hover:bg-zinc-200",
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex flex-col items-center gap-2 border p-4 transition ${colorClasses[color]} disabled:opacity-50`}
    >
      <Icon className="h-5 w-5" />
      <span className="font-mono text-xs font-bold uppercase tracking-wider">{label}</span>
      <span className="font-mono text-[10px] opacity-70">{time}</span>
    </button>
  );
}