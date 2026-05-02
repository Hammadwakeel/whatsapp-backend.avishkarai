"use client";

import { useEffect, useState } from "react";
import { Activity, Wifi, MessageSquare, MapPin, Calendar, Brain } from "lucide-react";
import { getApiBaseUrl, getStoredToken, bookingAPI, wikiAPI, journeyAPI, whatsappAPI } from "@/lib/api";

type ModuleStatus = {
  name: string;
  status: "active" | "inactive" | "unknown";
  info: string;
};

export default function DashboardOpsStatus() {
  const [modules, setModules] = useState<ModuleStatus[]>([
    { name: "API", status: "unknown", info: "..." },
    { name: "WhatsApp", status: "unknown", info: "..." },
    { name: "Journey", status: "unknown", info: "..." },
    { name: "Booking", status: "unknown", info: "..." },
    { name: "Knowledge", status: "unknown", info: "..." },
  ]);

  useEffect(() => {
    const fetchStatus = async () => {
      const token = getStoredToken();
      if (!token) return;

      const newModules: ModuleStatus[] = [];

      // API Status
      try {
        const response = await fetch(`${getApiBaseUrl()}/auth/profile`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          newModules.push({ name: "API", status: "active", info: "Connected" });
        } else {
          newModules.push({ name: "API", status: "inactive", info: "Error" });
        }
      } catch {
        newModules.push({ name: "API", status: "inactive", info: "Offline" });
      }

      // WhatsApp Status
      try {
        const session = await whatsappAPI.getSession();
        if (session) {
          newModules.push({ name: "WhatsApp", status: "active", info: session.status || "Connected" });
        } else {
          newModules.push({ name: "WhatsApp", status: "inactive", info: "Not connected" });
        }
      } catch {
        newModules.push({ name: "WhatsApp", status: "unknown", info: "..." });
      }

      // Journey Status
      try {
        const config = await journeyAPI.getConfig();
        newModules.push({
          name: "Journey",
          status: config.is_enabled ? "active" : "inactive",
          info: config.is_enabled ? "Enabled" : "Disabled"
        });
      } catch {
        newModules.push({ name: "Journey", status: "unknown", info: "..." });
      }

      // Booking Status
      try {
        const stats = await bookingAPI.getStats();
        newModules.push({
          name: "Booking",
          status: stats.total_active > 0 ? "active" : "inactive",
          info: `${stats.today_checkins} checkins / ${stats.today_checkouts} checkouts today`
        });
      } catch {
        newModules.push({ name: "Booking", status: "unknown", info: "..." });
      }

      // Knowledge Status
      try {
        const index = await wikiAPI.getIndex();
        newModules.push({
          name: "Knowledge",
          status: index.total_pages > 0 ? "active" : "inactive",
          info: `${index.total_pages} pages / ${index.total_vectors} vectors`
        });
      } catch {
        newModules.push({ name: "Knowledge", status: "unknown", info: "..." });
      }

      setModules(newModules);
    };

    fetchStatus();
    const timer = window.setInterval(fetchStatus, 30000);
    return () => window.clearInterval(timer);
  }, []);

  const getStatusColor = (status: ModuleStatus["status"]) => {
    switch (status) {
      case "active": return "bg-green-500";
      case "inactive": return "bg-zinc-400";
      default: return "bg-zinc-300 animate-pulse";
    }
  };

  const getStatusTextColor = (status: ModuleStatus["status"]) => {
    switch (status) {
      case "active": return "text-green-600";
      case "inactive": return "text-zinc-500";
      default: return "text-zinc-400";
    }
  };

  const getModuleIcon = (name: string) => {
    switch (name) {
      case "WhatsApp": return MessageSquare;
      case "Journey": return MapPin;
      case "Booking": return Calendar;
      case "Knowledge": return Brain;
      default: return Wifi;
    }
  };

  return (
    <div className="border border-black bg-white p-8">
      <div className="mb-5 flex items-center gap-2">
        <Activity className="h-4 w-4" />
        <p className="text-[10px] font-black uppercase tracking-[0.24em] text-zinc-500">
          System Health
        </p>
      </div>

      <div className="space-y-3">
        {modules.map((module, index) => {
          const Icon = getModuleIcon(module.name);
          return (
            <div key={index} className="flex items-center justify-between border border-black/15 px-4 py-3">
              <div className="flex items-center gap-3">
                <div className={`h-2 w-2 rounded-full ${getStatusColor(module.status)}`} />
                <Icon className="h-4 w-4 text-zinc-500" />
                <p className="text-sm font-black tracking-tight">{module.name}</p>
              </div>
              <p className={`text-[11px] font-mono uppercase tracking-[0.16em] ${getStatusTextColor(module.status)}`}>
                {module.info}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}