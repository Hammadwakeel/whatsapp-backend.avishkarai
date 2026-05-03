"use client";

import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import {
  Loader2,
  MessageCircle,
  MoreVertical,
  Search,
  Send,
  Phone,
} from "lucide-react";
import { whatsappAPI, type WhatsAppMessageRecord } from "@/lib/api";

const WA_BG = "#0b141a";
const WA_SIDEBAR = "#111b21";
const WA_PANEL = "#202c33";
const WA_INCOMING = "#202c33";
const WA_OUTGOING = "#005c4b";
const WA_TEXT = "#e9edef";
const WA_MUTED = "#8696a0";

function digitsOnly(s: string): string {
  return s.replace(/\D/g, "");
}

function peerKey(m: WhatsAppMessageRecord): string {
  const raw =
    m.direction === "inbound" ? m.from_number : m.to_number || m.from_number;
  const d = digitsOnly(raw);
  return d || raw.trim();
}

function formatPeerLabel(peerDigits: string): string {
  if (!peerDigits) return "Unknown";
  if (peerDigits.length >= 10) {
    return `+${peerDigits}`;
  }
  return peerDigits;
}

function initials(peerDigits: string): string {
  if (peerDigits.length >= 2) return peerDigits.slice(-2);
  return "?";
}

type ChatSummary = {
  peer: string;
  label: string;
  lastSnippet: string;
  lastTime: number;
};

function buildChatSummaries(msgs: WhatsAppMessageRecord[]): ChatSummary[] {
  const map = new Map<string, ChatSummary>();
  for (const m of msgs) {
    const peer = peerKey(m);
    if (!peer) continue;
    const t = new Date(m.created_at).getTime();
    const prev = map.get(peer);
    if (!prev || t > prev.lastTime) {
      map.set(peer, {
        peer,
        label: formatPeerLabel(peer),
        lastSnippet: m.content.slice(0, 56) + (m.content.length > 56 ? "…" : ""),
        lastTime: t,
      });
    }
  }
  return Array.from(map.values()).sort((a, b) => b.lastTime - a.lastTime);
}

function threadMessages(msgs: WhatsAppMessageRecord[], peer: string): WhatsAppMessageRecord[] {
  return msgs
    .filter((m) => peerKey(m) === peer)
    .sort(
      (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
}

function wikiSourceLine(msg: WhatsAppMessageRecord): string | null {
  const w = msg.wiki_sources;
  if (!w || typeof w !== "object") return null;
  const sources = (w as { sources?: string[] }).sources;
  if (sources?.length) return sources.join(" · ");
  return null;
}

/** Evolution / backend accept local or international digit strings */
function toSendAddress(peerDigits: string): string {
  return peerDigits.startsWith("+") ? peerDigits : peerDigits;
}

function QrDisplay({ raw }: { raw: string }) {
  const q = raw.trim();
  if (q.startsWith("data:image")) {
    return (
      <img src={q} alt="WhatsApp QR Code" className="h-56 w-56 object-contain" />
    );
  }
  const compact = q.replace(/\s/g, "");
  if (compact.length > 80 && /^[A-Za-z0-9+/=]+$/.test(compact)) {
    return (
      <img
        src={`data:image/png;base64,${compact}`}
        alt="WhatsApp QR Code"
        className="h-56 w-56 object-contain"
      />
    );
  }
  return (
    <pre className="max-w-xs overflow-auto whitespace-pre-wrap text-left text-xs text-zinc-600">
      {q.slice(0, 400)}
    </pre>
  );
}

export default function WhatsAppPage() {
  return (
    <div className="h-[100dvh] overflow-hidden" style={{ backgroundColor: WA_BG }}>
      <WhatsAppShell />
    </div>
  );
}

function WhatsAppShell() {
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<WhatsAppMessageRecord[]>([]);
  const [selectedPeer, setSelectedPeer] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarQuery, setSidebarQuery] = useState("");
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [qrLoading, setQrLoading] = useState(false);
  const [evolutionHint, setEvolutionHint] = useState<string | null>(null);
  const [reconnectRequired, setReconnectRequired] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);

  // SSE event source ref
  const sseRef = useRef<EventSource | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const status = await whatsappAPI.getStatus();
      const ok =
        status.is_connected === true ||
        (status.status || "").toUpperCase() === "CONNECTED" ||
        (status.status || "").toUpperCase() === "OPEN";
      setConnected(ok);

      // If disconnected unexpectedly
      if (!ok && status.status === "DISCONNECTED") {
        setReconnectRequired(true);
      }

      const data = await whatsappAPI.getMessages(250, "desc", 1);
      setMessages(data.messages);
      setError(null);
    } catch (e) {
      console.error(e);
      setError("Could not load messages");
    } finally {
      setLoading(false);
    }
  }, []);

  // Setup SSE for real-time updates
  useEffect(() => {
    if (!sseRef.current) {
      const eventSource = whatsappAPI.connectSSE((type, data) => {
        switch (type) {
          case "connected":
            setSseConnected(true);
            console.log("SSE connected:", data);
            break;

          case "new_message":
            // Add new message to the list
            setMessages((prev) => {
              const newMsg = data as unknown as WhatsAppMessageRecord;
              // Check if message already exists
              if (prev.some((m) => m.id === newMsg.id)) return prev;
              return [newMsg, ...prev];
            });
            break;

          case "connection_state":
            if (data.state === "CONNECTED") {
              setConnected(true);
              setReconnectRequired(false);
              loadAll();
            } else if (data.state === "DISCONNECTED" || data.state === "RESET") {
              setConnected(false);
              setQrCode(null);
            }
            break;

          case "session_disconnected":
            setConnected(false);
            setReconnectRequired(true);
            setError(data.message as string || "WhatsApp session disconnected");
            break;

          case "whatsapp_status":
            if (data.is_connected) {
              setConnected(true);
              setReconnectRequired(false);
            }
            break;
        }
      });

      sseRef.current = eventSource;

      eventSource.onerror = () => {
        setSseConnected(false);
        // SSE will auto-reconnect, but if it fails multiple times, fallback to polling
        console.log("SSE connection lost, will retry...");
      };
    }

    return () => {
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
        setSseConnected(false);
      }
    };
  }, [loadAll]);

  // Initial load
  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Handle visibility change - refresh when tab becomes visible
  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === "visible") loadAll();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [loadAll]);

  // Only poll if SSE is not connected (fallback)
  useEffect(() => {
    if (connected && sseConnected) return; // SSE handles updates

    const t = window.setInterval(loadAll, 30000); // Reduced polling to 30s when connected
    return () => window.clearInterval(t);
  }, [connected, sseConnected, loadAll]);

  useEffect(() => {
    if (!qrCode || connected) return;
    const poll = async () => {
      try {
        const st = await whatsappAPI.getStatus();
        const ok =
          st.is_connected === true ||
          (st.status || "").toUpperCase() === "CONNECTED" ||
          (st.status || "").toUpperCase() === "OPEN";
        if (ok) {
          setQrCode(null);
          setConnected(true);
          await loadAll();
          return;
        }
        if (st.qrcode) setQrCode(st.qrcode);
      } catch {
        /* ignore */
      }
    };
    poll();
    const id = window.setInterval(poll, 2500);
    return () => window.clearInterval(id);
  }, [qrCode, connected, loadAll]);

  const chats = useMemo(() => buildChatSummaries(messages), [messages]);

  const filteredChats = useMemo(() => {
    const q = sidebarQuery.trim().toLowerCase();
    if (!q) return chats;
    return chats.filter(
      (c) =>
        c.label.toLowerCase().includes(q) ||
        c.peer.includes(q) ||
        c.lastSnippet.toLowerCase().includes(q),
    );
  }, [chats, sidebarQuery]);

  useEffect(() => {
    if (!selectedPeer && filteredChats.length > 0) {
      setSelectedPeer(filteredChats[0].peer);
    }
  }, [filteredChats, selectedPeer]);

  const activeThread = useMemo(() => {
    if (!selectedPeer) return [];
    return threadMessages(messages, selectedPeer);
  }, [messages, selectedPeer]);

  const activeSummary = useMemo(
    () => chats.find((c) => c.peer === selectedPeer),
    [chats, selectedPeer],
  );

  const connectFlow = async () => {
    setQrLoading(true);
    setEvolutionHint(null);
    setQrCode(null);
    try {
      const result = await whatsappAPI.connect();
      if (result.evolution_detail) setEvolutionHint(result.evolution_detail);
      if (result.qr_code) {
        setQrCode(result.qr_code);
      }
      if (result.status === "connected") {
        await loadAll();
        return;
      }
      if (result.status === "waiting" || !result.qr_code) {
        for (let i = 0; i < 20; i++) {
          await new Promise((r) => setTimeout(r, 1500));
          const st = await whatsappAPI.getStatus();
          if (st.qrcode) {
            setQrCode(st.qrcode);
            break;
          }
          const ok =
            st.is_connected === true ||
            (st.status || "").toUpperCase() === "CONNECTED";
          if (ok) {
            await loadAll();
            return;
          }
          if (st.evolution_detail) setEvolutionHint(st.evolution_detail);
        }
      }
      await loadAll();
    } catch {
      setEvolutionHint("Connect failed — check Evolution API and backend logs.");
    } finally {
      setQrLoading(false);
    }
  };

  const disconnectFlow = async () => {
    if (!confirm("Disconnect WhatsApp on this device?")) return;
    await whatsappAPI.disconnect();
    setConnected(false);
    setQrCode(null);
    setReconnectRequired(false);
    await loadAll();
  };

  const resetSessionFlow = async () => {
    if (!confirm("Reset WhatsApp session? This will disconnect and generate a new QR code.")) return;
    setQrLoading(true);
    setError(null);
    try {
      const result = await whatsappAPI.resetSession();
      if (result.qr_code) {
        setQrCode(result.qr_code);
        setReconnectRequired(false);
      }
      if (result.evolution_detail) setEvolutionHint(result.evolution_detail);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setQrLoading(false);
    }
  };

  const sendDraft = async () => {
    if (!draft.trim() || !selectedPeer || sending) return;
    setSending(true);
    setError(null);
    try {
      await whatsappAPI.sendMessage(toSendAddress(selectedPeer), draft.trim());
      setDraft("");
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Send failed");
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center" style={{ color: WA_MUTED }}>
        <Loader2 className="h-10 w-10 animate-spin" />
      </div>
    );
  }

  if (!connected) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-6 px-6 text-center">
        <div
          className="rounded-full p-6"
          style={{ backgroundColor: WA_PANEL }}
        >
          <MessageCircle className="h-14 w-14" style={{ color: WA_TEXT }} />
        </div>
        <div>
          <h1 className="text-xl font-medium" style={{ color: WA_TEXT }}>
            {reconnectRequired ? "WhatsApp Session Lost" : "WhatsApp Web"}
          </h1>
          <p className="mt-2 max-w-md text-sm" style={{ color: WA_MUTED }}>
            {reconnectRequired
              ? "Your WhatsApp session was disconnected. Click below to reset and scan a new QR code."
              : "Link your phone to see guest chats here. Incoming messages are answered automatically by your agent using the Knowledge base (wiki RAG)."}
          </p>
        </div>
        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}
        <div className="flex gap-3">
          {reconnectRequired ? (
            <button
              type="button"
              onClick={resetSessionFlow}
              disabled={qrLoading}
              className="flex items-center gap-2 rounded px-6 py-3 text-sm font-medium text-white"
              style={{ backgroundColor: "#00a884" }}
            >
              {qrLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Phone className="h-4 w-4" />}
              Reset & Reconnect
            </button>
          ) : (
            <button
              type="button"
              onClick={connectFlow}
              disabled={qrLoading}
              className="flex items-center gap-2 rounded px-6 py-3 text-sm font-medium text-white"
              style={{ backgroundColor: "#00a884" }}
            >
              {qrLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Phone className="h-4 w-4" />}
              Link with phone number
            </button>
          )}
        </div>
        {qrCode && (
          <div className="rounded-lg border border-white/10 bg-black/20 p-6">
            <QrDisplay raw={qrCode} />
            {evolutionHint && (
              <p className="mt-4 max-w-sm text-xs text-amber-200/90">{evolutionHint}</p>
            )}
            <p className="mt-4 text-xs" style={{ color: WA_MUTED }}>
              Scan with WhatsApp → Linked devices → Link a device
            </p>
          </div>
        )}
        {sseConnected && (
          <p className="text-xs" style={{ color: WA_MUTED }}>
            Live updates active
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Sidebar — chat list */}
      <aside
        className="flex w-full max-w-[400px] flex-shrink-0 flex-col border-r border-black/30 md:max-w-[380px]"
        style={{ backgroundColor: WA_SIDEBAR }}
      >
        <header
          className="flex h-14 flex-shrink-0 items-center justify-between px-3"
          style={{ backgroundColor: WA_PANEL }}
        >
          <span className="font-semibold tracking-tight" style={{ color: WA_TEXT }}>
            WhatsApp
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Disconnect"
              onClick={disconnectFlow}
              className="rounded p-2 hover:bg-white/10"
              style={{ color: WA_MUTED }}
            >
              <MoreVertical className="h-5 w-5" />
            </button>
          </div>
        </header>
        <div className="px-2 py-2">
          <div
            className="flex items-center gap-2 rounded-lg px-3 py-2"
            style={{ backgroundColor: WA_PANEL }}
          >
            <Search className="h-4 w-4 flex-shrink-0" style={{ color: WA_MUTED }} />
            <input
              type="search"
              placeholder="Search or start new chat"
              value={sidebarQuery}
              onChange={(e) => setSidebarQuery(e.target.value)}
              className="w-full bg-transparent text-sm outline-none placeholder:text-[#8696a0]"
              style={{ color: WA_TEXT }}
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {filteredChats.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm" style={{ color: WA_MUTED }}>
              No chats yet. When guests message your WhatsApp number, threads appear here.
              Auto-replies use your wiki knowledge via /webhook/whatsapp.
            </p>
          ) : (
            filteredChats.map((c) => (
              <button
                key={c.peer}
                type="button"
                onClick={() => setSelectedPeer(c.peer)}
                className="flex w-full items-center gap-3 px-3 py-3 text-left transition hover:bg-white/5"
                style={{
                  backgroundColor:
                    selectedPeer === c.peer ? "rgba(255,255,255,0.06)" : "transparent",
                }}
              >
                <div
                  className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full text-lg font-medium text-white"
                  style={{ backgroundColor: "#6b7c85" }}
                >
                  {initials(c.peer)}
                </div>
                <div className="min-w-0 flex-1 border-b border-white/5 pb-3 pt-1">
                  <div className="flex justify-between gap-2">
                    <span
                      className="truncate font-medium"
                      style={{ color: WA_TEXT }}
                    >
                      {c.label}
                    </span>
                    <span className="flex-shrink-0 text-[11px]" style={{ color: WA_MUTED }}>
                      {new Date(c.lastTime).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <p className="truncate text-sm" style={{ color: WA_MUTED }}>
                    {c.lastSnippet}
                  </p>
                </div>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* Main conversation */}
      <section className="flex min-w-0 flex-1 flex-col">
        <header
          className="flex h-14 flex-shrink-0 items-center gap-3 px-4"
          style={{ backgroundColor: WA_PANEL }}
        >
          <div
            className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full text-sm font-medium text-white"
            style={{ backgroundColor: "#6b7c85" }}
          >
            {activeSummary ? initials(activeSummary.peer) : "—"}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium" style={{ color: WA_TEXT }}>
              {activeSummary?.label || "Select a chat"}
            </div>
            <div className="truncate text-xs" style={{ color: WA_MUTED }}>
              {connected ? "Agent replies use wiki RAG · Evolution webhook" : ""}
            </div>
          </div>
        </header>

        <div
          className="relative flex-1 overflow-y-auto px-[8%] py-4"
          style={{
            backgroundColor: WA_BG,
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        >
          {error && (
            <div className="mb-3 rounded bg-red-900/40 px-3 py-2 text-sm text-red-200">
              {error}
            </div>
          )}
          <div className="mx-auto flex max-w-3xl flex-col gap-1">
            {activeThread.map((msg) => {
              const inbound = msg.direction === "inbound";
              const wiki = wikiSourceLine(msg);
              return (
                <div
                  key={msg.id}
                  className={`flex w-full ${inbound ? "justify-start" : "justify-end"}`}
                >
                  <div
                    className="max-w-[75%] rounded-lg px-3 py-2 shadow-sm"
                    style={{
                      backgroundColor: inbound ? WA_INCOMING : WA_OUTGOING,
                      color: WA_TEXT,
                    }}
                  >
                    <p className="whitespace-pre-wrap text-[14.2px] leading-relaxed">
                      {msg.content}
                    </p>
                    {!inbound && (
                      <div className="mt-1 space-y-0.5 border-t border-white/10 pt-1 text-[11px]" style={{ color: WA_MUTED }}>
                        {wiki && (
                          <p>
                            <span className="font-medium text-emerald-300/90">Wiki · </span>
                            {wiki}
                          </p>
                        )}
                        {msg.web_search_used && (
                          <p className="text-sky-300/90">Web search was used</p>
                        )}
                        {!wiki && !msg.web_search_used && (
                          <p className="italic opacity-80">Agent / automated reply</p>
                        )}
                      </div>
                    )}
                    <div className="mt-1 text-right text-[11px] opacity-70">
                      {new Date(msg.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <footer className="flex-shrink-0 px-[8%] pb-4 pt-2">
          <div
            className="mx-auto flex max-w-3xl items-end gap-2 rounded-lg px-3 py-2"
            style={{ backgroundColor: WA_PANEL }}
          >
            <textarea
              rows={1}
              placeholder={
                selectedPeer
                  ? "Type a message"
                  : "Select a chat to reply"
              }
              disabled={!selectedPeer || sending}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendDraft();
                }
              }}
              className="max-h-32 min-h-[44px] flex-1 resize-none bg-transparent py-2 text-sm outline-none placeholder:text-[#8696a0]"
              style={{ color: WA_TEXT }}
            />
            <button
              type="button"
              disabled={!selectedPeer || !draft.trim() || sending}
              onClick={sendDraft}
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full disabled:opacity-40"
              style={{ backgroundColor: "#00a884", color: "#fff" }}
              aria-label="Send"
            >
              {sending ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </button>
          </div>
          <p className="mx-auto mt-2 max-w-3xl text-center text-[11px]" style={{ color: WA_MUTED }}>
            Guest messages hit POST /webhook/whatsapp → Agent (wiki search + LLM) → reply sent via Evolution.
            Set WEBHOOK_WHATSAPP_TENANT_ID in production if you run multiple hotels.
          </p>
        </footer>
      </section>
    </div>
  );
}
