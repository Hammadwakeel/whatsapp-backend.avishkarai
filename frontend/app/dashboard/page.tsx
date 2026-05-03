"use client";

import Link from "next/link";
import {
  ArrowRight,
  Brain,
  CalendarSync,
  MessageSquare,
  Route,
  User,
  Loader2,
} from "lucide-react";
import { useEffect, useState } from "react";
import DashboardRecentActivity from "@/components/DashboardRecentActivity";
import DashboardOpsStatus from "@/components/DashboardOpsStatus";
import AppNav from "@/components/AppNav";
import { getStoredTenant, getStoredToken, clearStoredAuth } from "@/lib/api";
import { useRouter } from "next/navigation";

const MODULES = [
  {
    href: "/whatsapp",
    title: "WHATSAPP HUB",
    body: "Handle live chats, handoff, and response operations from one stream.",
    icon: MessageSquare,
  },
  {
    href: "/journey",
    title: "JOURNEY ENGINE",
    body: "Run check-in to checkout flows with reusable automation templates.",
    icon: Route,
  },
  {
    href: "/booking",
    title: "BOOKING SYNC",
    body: "Track reservations and keep hotel data refreshed in one place.",
    icon: CalendarSync,
  },
  {
    href: "/knowledge",
    title: "KNOWLEDGE + RAG",
    body: "Upload docs and route retrieval-backed answers to assistants.",
    icon: Brain,
  },
  {
    href: "/profile",
    title: "OPERATOR PROFILE",
    body: "Manage identity, account details, and session metadata.",
    icon: User,
  },
];

export default function DashboardPage() {
  const router = useRouter();
  const [tenant, setTenant] = useState<{ name?: string; hotel_name?: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.push("/login");
      return;
    }

    const storedTenant = getStoredTenant();
    if (storedTenant) {
      setTenant({ name: storedTenant.name, hotel_name: storedTenant.hotel_name ?? undefined });
    } else {
      setTenant(null);
    }
    setLoading(false);
  }, [router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-white" />
          <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.4em] text-white/50">
            Loading Dashboard...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-white font-sans text-black selection:bg-black selection:text-white">
      {/* Module Cards Section */}
      <section className="border-y border-black px-6 py-12">
          <div className="mx-auto max-w-7xl">
            <div className="mb-6 flex items-center gap-4">
              <h2 className="whitespace-nowrap text-[11px] font-black uppercase tracking-[0.35em]">
                Active Modules
              </h2>
              <div className="h-px flex-grow bg-black" />
              {tenant?.hotel_name && (
                <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
                  {tenant.hotel_name}
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {MODULES.map((mod) => (
                <ModuleCard
                  key={mod.href}
                  href={mod.href}
                  title={mod.title}
                  body={mod.body}
                  icon={mod.icon}
                />
              ))}
            </div>
          </div>
        </section>

        {/* Activity Section */}
        <section className="bg-zinc-50 px-6 py-16">
          <div className="mx-auto max-w-7xl">
            <div className="mb-8 flex items-end justify-between gap-6">
              <div>
                <p className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">
                  Real-Time Feed
                </p>
                <h3 className="mt-2 text-4xl font-black tracking-tight md:text-6xl">RECENT ACTIVITIES</h3>
              </div>
              <span className="text-[10px] font-black uppercase tracking-[0.24em] text-zinc-500">
                INIKA CONTROL
              </span>
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <DashboardRecentActivity />
              <DashboardOpsStatus />
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-black bg-black px-6 py-10 text-white">
          <div className="mx-auto flex max-w-7xl flex-col justify-between gap-3 text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500 md:flex-row">
            <span>// Secure_Channel_Active //</span>
            <span>Digital Hotel Theme</span>
            <span>Dashboard Session: Operational</span>
          </div>
        </footer>
      </div>
  );
}

function ModuleCard({
  href,
  title,
  body,
  icon: Icon,
}: {
  href: string;
  title: string;
  body: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Link
      href={href}
      className="rounded-none border border-black bg-white p-8 shadow-sm transition hover:-translate-y-0.5 hover:bg-zinc-100 hover:shadow-md"
    >
      <Icon className="mb-5 h-5 w-5" />
      <h4 className="text-xl font-black tracking-tight">{title}</h4>
      <p className="mt-3 text-sm leading-relaxed text-zinc-600">{body}</p>
      <span className="mt-6 inline-flex items-center gap-2 border border-black px-3 py-2 text-[10px] font-black uppercase tracking-[0.22em]">
        Launch Module
        <ArrowRight className="h-3 w-3" />
      </span>
    </Link>
  );
}