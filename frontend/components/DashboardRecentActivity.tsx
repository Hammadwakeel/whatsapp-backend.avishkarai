"use client";

import { useEffect, useState } from "react";
import { Activity, Clock, MessageSquare, Send, User } from "lucide-react";
import { whatsappAPI, journeyAPI, getStoredToken } from "@/lib/api";

type ActivityItem = {
  id: string;
  type: "message" | "journey" | "booking" | "system";
  title: string;
  description: string;
  time: string;
};

export default function DashboardRecentActivity() {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchActivity = async () => {
      try {
        const activities: ActivityItem[] = [];

        // Get recent WhatsApp messages
        try {
          const messages = await whatsappAPI.getMessages(5);
          messages.messages.forEach((msg) => {
            activities.push({
              id: `msg-${msg.id}`,
              type: "message",
              title: msg.direction === "inbound" ? `From ${msg.from}` : `To ${msg.to}`,
              description: msg.content.substring(0, 50) + (msg.content.length > 50 ? "..." : ""),
              time: new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            });
          });
        } catch {
          // WhatsApp not connected
        }

        // Get recent Journey logs
        try {
          const logs = await journeyAPI.getLogs(5);
          logs.logs.forEach((log) => {
            activities.push({
              id: `log-${log.id}`,
              type: "journey",
              title: `${log.message_type} message`,
              description: `Sent to ${log.guest_name}: ${log.content.substring(0, 40)}...`,
              time: new Date(log.sent_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            });
          });
        } catch {
          // Journey not configured
        }

        // Sort by time (most recent first) and limit
        activities.sort((a, b) => b.time.localeCompare(a.time));
        setItems(activities.slice(0, 10));
      } catch {
        // Handle errors silently
      } finally {
        setLoading(false);
      }
    };

    fetchActivity();
    const timer = window.setInterval(fetchActivity, 15000);
    return () => window.clearInterval(timer);
  }, []);

  const getActivityIcon = (type: ActivityItem["type"]) => {
    switch (type) {
      case "message": return MessageSquare;
      case "journey": return Send;
      case "booking": return User;
      default: return Activity;
    }
  };

  const getActivityColor = (type: ActivityItem["type"]) => {
    switch (type) {
      case "message": return "text-blue-600";
      case "journey": return "text-green-600";
      case "booking": return "text-purple-600";
      default: return "text-zinc-600";
    }
  };

  return (
    <div className="border border-black bg-white p-8">
      <div className="mb-5 flex items-center gap-2">
        <Activity className="h-4 w-4" />
        <p className="text-[10px] font-black uppercase tracking-[0.24em] text-zinc-500">
          Recent Activity
        </p>
      </div>

      {loading ? (
        <div className="border border-black/15 px-4 py-6">
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 animate-pulse bg-zinc-100" />
            ))}
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="border border-black/15 px-4 py-6 text-sm text-zinc-500">
          <p>No recent activity.</p>
          <p className="mt-1 text-xs">Connect WhatsApp or enable Journey to see activity here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item, index) => {
            const Icon = getActivityIcon(item.type);
            return (
              <div
                key={item.id}
                className="flex items-start justify-between gap-4 border border-black/15 px-4 py-3"
              >
                <div className="flex items-start gap-3">
                  <Icon className={`mt-0.5 h-4 w-4 ${getActivityColor(item.type)}`} />
                  <div>
                    <p className="text-sm font-black tracking-tight">{item.title}</p>
                    <p className="mt-1 text-sm text-zinc-700">{item.description}</p>
                  </div>
                </div>
                <p className="flex shrink-0 items-center gap-1 text-[10px] font-mono uppercase tracking-[0.16em] text-zinc-500">
                  <Clock className="h-3 w-3" />
                  {item.time}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}