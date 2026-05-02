"use client";

import { useEffect, useState, useRef } from "react";
import { MessageSquare, Send, Loader2, Search, X, RefreshCw, RotateCcw, Check } from "lucide-react";
import { whatsappAPI, WhatsAppSession } from "@/lib/api";
import NavigationWrapper from "@/components/NavigationWrapper";

function formatJid(jid: string): string {
  const match = jid.match(/^(\d+)@/);
  if (match) {
    const num = match[1];
    if (num.startsWith("92") && num.length === 12) {
      return `+${num.slice(0, 2)} ${num.slice(2, 5)} ${num.slice(5)}`;
    }
    return num;
  }
  return jid.split("@")[0];
}

function formatTime(timestamp: string) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: true });
}

function formatDate(timestamp: string) {
  const date = new Date(timestamp);
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

export default function WhatsAppPage() {
  return (
    <NavigationWrapper>
      <ChatView />
    </NavigationWrapper>
  );
}

function ChatView() {
  const [session, setSession] = useState<WhatsAppSession | null>(null);
  const [messages, setMessages] = useState<Array<{ id: string; from: string; to: string; content: string; timestamp: string; direction: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [sending, setSending] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSession();
  }, []);

  const loadSession = async () => {
    setLoading(true);
    try {
      const sess = await whatsappAPI.getSession();
      setSession(sess);
      if (sess) {
        loadMessages();
      }
    } catch (err) {
      console.error("Failed to load session:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async () => {
    try {
      const data = await whatsappAPI.getMessages(50);
      setMessages(data.messages);
    } catch (err) {
      console.error("Failed to load messages:", err);
    }
  };

  const connectWhatsApp = async () => {
    setRefreshing(true);
    try {
      const sess = await whatsappAPI.connect();
      setSession(sess);
    } catch (err) {
      setError("Failed to connect WhatsApp");
    } finally {
      setRefreshing(false);
    }
  };

  const disconnectWhatsApp = async () => {
    if (!confirm("Disconnect WhatsApp? You will need to scan QR again.")) return;
    try {
      await whatsappAPI.disconnect();
      setSession(null);
      setMessages([]);
    } catch (err) {
      setError("Failed to disconnect");
    }
  };

  const sendMessage = async (to: string, text: string) => {
    setSending(true);
    try {
      await whatsappAPI.sendMessage(to, text);
      loadMessages();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to send";
      setError(msg);
    } finally {
      setSending(false);
    }
  };

  const handleSend = () => {
    if (!draft.trim() || sending) return;
    // Get the first conversation's contact or prompt for it
    const firstMsg = messages.find(m => m.direction === "inbound");
    if (!firstMsg) {
      setError("No contact to send to. Wait for an incoming message first.");
      return;
    }
    sendMessage(firstMsg.from, draft.trim());
    setDraft("");
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-white px-6 py-12">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <header className="mb-10 border-y border-black bg-white px-6 py-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center border border-black bg-black text-white">
                <MessageSquare className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-3xl font-black tracking-tight uppercase">WhatsApp Hub</h1>
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  Multi-device messaging gateway
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <StatusBadge
                label="Connection"
                value={session ? "Linked" : "Not Connected"}
                ok={!!session}
              />
              <StatusBadge
                label="Status"
                value={session?.status?.toUpperCase() || "OFFLINE"}
                ok={!!session}
              />
            </div>
          </div>
        </header>

        {/* Error */}
        {error && (
          <div className="mb-6 border border-red-500 bg-red-50 px-4 py-3">
            <p className="font-mono text-xs text-red-600">ERROR: {error}</p>
          </div>
        )}

        {/* Not Connected - Show Connect Options */}
        {!session && (
          <div className="mb-8 border border-black p-8 text-center">
            <div className="mb-6">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center border border-black bg-gray-50">
                <MessageSquare className="h-6 w-6" />
              </div>
              <h3 className="font-mono text-lg font-bold uppercase tracking-tight">
                Connect WhatsApp
              </h3>
              <p className="font-mono text-xs text-gray-500 mt-2">
                Connect your WhatsApp to start messaging guests
              </p>
            </div>

            <div className="mt-6 flex items-center justify-center gap-4">
              <button
                onClick={connectWhatsApp}
                disabled={refreshing}
                className="flex items-center gap-2 border border-black bg-black px-6 py-3 font-mono text-sm font-medium text-white transition-all hover:bg-gray-800 disabled:opacity-50"
              >
                {refreshing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <MessageSquare className="h-4 w-4" />
                )}
                Connect WhatsApp
              </button>
            </div>
          </div>
        )}

        {/* Connected - Show Messages */}
        {session && (
          <div className="border border-black">
            {/* Session Info Bar */}
            <div className="border-b border-black bg-black px-6 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Check className="h-4 w-4 text-green-500" />
                  <span className="font-mono text-sm font-semibold uppercase text-white tracking-wider">
                    Connected as {session.profile_name || session.phone || "WhatsApp"}
                  </span>
                </div>
                <button
                  onClick={disconnectWhatsApp}
                  className="flex items-center gap-2 border border-red-500 px-4 py-2 font-mono text-xs font-medium text-red-500 transition hover:bg-red-500 hover:text-white"
                >
                  <RotateCcw className="h-3 w-3" />
                  Disconnect
                </button>
              </div>
            </div>

            {/* Messages Area */}
            <div className="flex h-[calc(100vh-400px)] flex-col">
              {/* Message List */}
              <div className="flex-1 overflow-y-auto p-6">
                {messages.length === 0 ? (
                  <div className="flex h-full items-center justify-center">
                    <div className="text-center">
                      <MessageSquare className="mx-auto mb-3 h-10 w-10 text-gray-300" />
                      <p className="font-mono text-sm text-gray-500">No messages yet</p>
                      <p className="mt-2 font-mono text-xs text-gray-400">
                        Messages from guests will appear here
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={`flex ${msg.direction === "outbound" ? "justify-end" : "justify-start"}`}
                      >
                        <div className={`max-w-[70%] border px-4 py-3 ${
                          msg.direction === "outbound"
                            ? "border-black bg-black text-white"
                            : "border-black bg-white text-black"
                        }`}>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-mono text-[10px] font-bold">
                              {msg.direction === "inbound" ? "From" : "To"}:
                            </span>
                            <span className="font-mono text-[10px]">
                              {msg.direction === "inbound" ? formatJid(msg.from) : formatJid(msg.to)}
                            </span>
                          </div>
                          <p className="font-mono text-sm leading-relaxed">{msg.content}</p>
                          <p className={`mt-2 font-mono text-[10px] ${msg.direction === "outbound" ? "text-gray-400" : "text-gray-500"}`}>
                            {formatDate(msg.timestamp)} {formatTime(msg.timestamp)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Quick Reply (Reply to last inbound) */}
              <div className="border-t border-black p-4">
                <div className="flex items-center gap-3">
                  <input
                    type="text"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    placeholder="Type a quick reply..."
                    disabled={sending}
                    className="input-field flex-1"
                  />
                  <button
                    onClick={handleSend}
                    disabled={sending || !draft.trim()}
                    className="flex items-center gap-2 border border-black bg-black px-6 py-3 font-mono text-sm font-medium text-white transition-all hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {sending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                    Send
                  </button>
                </div>
                <p className="mt-2 font-mono text-[10px] text-gray-500">
                  Press Enter to send. Reply will go to the most recent contact.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <footer className="mt-16 border-t border-black bg-black px-6 py-8">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">
            <span>WhatsApp Hub v1.0</span>
            <span>Inika Bot</span>
          </div>
        </footer>
      </div>
    </NavigationWrapper>
  );
}

function StatusBadge({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2 border border-black px-3 py-1.5">
      <span className={`h-2 w-2 ${ok ? "bg-green-500" : "bg-amber-500 animate-pulse"}`}></span>
      <span className="font-mono text-xs font-medium text-black uppercase tracking-wider">{label}</span>
      <span className="font-mono text-xs text-gray-500">:</span>
      <span className="font-mono text-xs font-semibold uppercase tracking-wider">{value}</span>
    </div>
  );
}