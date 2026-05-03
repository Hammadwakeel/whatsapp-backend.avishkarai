"use client";

import { useEffect, useState } from "react";
import { Calendar, RefreshCw, Loader2, CheckCircle, XCircle, Clock, Users, Bed } from "lucide-react";
import { bookingAPI, BookingGuest, BookingStats } from "@/lib/api";


export default function BookingPage() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-white">
      <BookingContent />
    </div>
  );
}

function BookingContent() {
  const [guests, setGuests] = useState<BookingGuest[]>([]);
  const [stats, setStats] = useState<BookingStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<string>("");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [guestsData, statsData] = await Promise.all([
        bookingAPI.getGuests(),
        bookingAPI.getStats(),
      ]);
      setGuests(guestsData.guests);
      setStats(statsData);
      setLastSync(new Date().toLocaleTimeString());
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load data";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const syncData = async () => {
    setSyncing(true);
    setError(null);
    try {
      await bookingAPI.sync();
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Sync failed";
      setError(msg);
    } finally {
      setSyncing(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      "Arrived": "bg-green-100 text-green-800 border-green-300",
      "StayOver": "bg-green-100 text-green-800 border-green-300",
      "Confirmed": "bg-blue-100 text-blue-800 border-blue-300",
      "Due In": "bg-amber-100 text-amber-800 border-amber-300",
      "Checkout": "bg-gray-100 text-gray-600 border-gray-300",
    };
    return colors[status] || "bg-gray-100 text-gray-800 border-gray-300";
  };

  const getStatusIcon = (status: string) => {
    if (status === "Arrived" || status === "StayOver") {
      return <CheckCircle className="h-4 w-4 text-green-600" />;
    }
    if (status === "Checkout") {
      return <XCircle className="h-4 w-4 text-gray-400" />;
    }
    return <Clock className="h-4 w-4 text-amber-500" />;
  };

  const arrivedCount = stats?.arrived || 0;
  const dueInCount = stats?.due_in || 0;
  const checkoutsToday = stats?.today_checkouts || 0;

  return (
    <div className="min-h-screen overflow-x-hidden bg-white px-6 py-12">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <header className="mb-10 border-y border-black bg-white px-6 py-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center border border-black bg-black text-white">
                <Calendar className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-3xl font-black tracking-tight uppercase">Booking Hub</h1>
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  Real-time guest reservations
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {lastSync && (
                <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-zinc-500">
                  Last sync: {lastSync}
                </div>
              )}
              <button
                onClick={syncData}
                disabled={syncing}
                className="flex items-center gap-2 border border-black bg-black px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-white transition hover:bg-zinc-800 disabled:opacity-50"
              >
                {syncing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Sync Bookings
              </button>
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

        {/* Stats */}
        {loading ? (
          <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-20 animate-pulse bg-zinc-100" />
            ))}
          </div>
        ) : (
          <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-4">
            <StatCard
              label="Total Active"
              value={stats?.total_active || 0}
              icon={Users}
              color="black"
            />
            <StatCard
              label="Checked In"
              value={arrivedCount}
              icon={CheckCircle}
              color="green"
            />
            <StatCard
              label="Due In"
              value={dueInCount}
              icon={Clock}
              color="amber"
            />
            <StatCard
              label="Checkouts Today"
              value={checkoutsToday}
              icon={XCircle}
              color="gray"
            />
          </div>
        )}

        {/* Guest Table */}
        <div className="border border-black">
          <div className="border-b border-black bg-black px-6 py-4">
            <h2 className="font-mono text-sm font-semibold uppercase tracking-wider text-white">
              Active Guests
            </h2>
          </div>

          {loading ? (
            <div className="p-6">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="mb-4 h-16 animate-pulse bg-zinc-100" />
              ))}
            </div>
          ) : guests.length === 0 ? (
            <div className="p-12 text-center">
              <Bed className="mx-auto mb-3 h-10 w-10 text-zinc-300" />
              <p className="font-mono text-sm text-zinc-500">No guests found</p>
              <p className="mt-2 font-mono text-xs text-zinc-400">
                Sync from booking system to load guests
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="px-4 py-3 text-left font-mono text-xs font-semibold uppercase text-gray-500">Guest</th>
                    <th className="px-4 py-3 text-left font-mono text-xs font-semibold uppercase text-gray-500">Room</th>
                    <th className="px-4 py-3 text-left font-mono text-xs font-semibold uppercase text-gray-500">Check In</th>
                    <th className="px-4 py-3 text-left font-mono text-xs font-semibold uppercase text-gray-500">Check Out</th>
                    <th className="px-4 py-3 text-left font-mono text-xs font-semibold uppercase text-gray-500">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {guests.map((guest, index) => (
                    <tr
                      key={`${guest.id}-${index}`}
                      className="border-b border-gray-100 transition hover:bg-zinc-50"
                    >
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center border border-black bg-gray-100 font-mono text-sm font-bold">
                            {guest.gname?.charAt(0) || "?"}
                          </div>
                          <div>
                            <p className="font-mono text-sm font-medium">{guest.gname}</p>
                            <p className="font-mono text-xs text-gray-400">{guest.mobile}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <span className="font-mono text-sm font-medium">{guest.room}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className="font-mono text-sm">{guest.cindate || "-"}</span>
                      </td>
                      <td className="px-4 py-4">
                        <span className="font-mono text-sm">{guest.coutdate || "-"}</span>
                      </td>
                      <td className="px-4 py-4">
                        <div className={`inline-flex items-center gap-1.5 border px-2 py-1 ${getStatusBadge(guest.gstatus)}`}>
                          {getStatusIcon(guest.gstatus)}
                          <span className="font-mono text-xs font-medium">{guest.gstatus}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="mt-16 border-t border-black bg-black px-6 py-8">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">
            <span>Booking Hub v1.0</span>
            <span>Inika Bot</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }: { label: string; value: number; icon: React.ComponentType<{ className?: string }>; color: string }) {
  const colorClasses: Record<string, string> = {
    black: "bg-black text-white border-black",
    green: "bg-green-100 text-green-800 border-green-300",
    amber: "bg-amber-100 text-amber-800 border-amber-300",
    gray: "bg-gray-100 text-gray-600 border-gray-300",
  };

  return (
    <div className={`border p-4 ${colorClasses[color]}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-xs font-semibold uppercase tracking-wider opacity-70">{label}</span>
        <Icon className="h-4 w-4" />
      </div>
      <div className="font-mono text-2xl font-bold">{value}</div>
    </div>
  );
}