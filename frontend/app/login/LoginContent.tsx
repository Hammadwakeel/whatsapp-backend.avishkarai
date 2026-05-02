"use client";

import Link from "next/link";
import { Loader2, ChevronRight, ShieldCheck, Check, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import MarketingNav from "@/components/MarketingNav";
import AxiomInput from "@/components/AxiomInput";
import { authAPI, setStoredAuth, getStoredTenant } from "@/lib/api";

export default function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Mode: login or signup
  const [mode, setMode] = useState<"login" | "signup">(
    searchParams.get("mode") === "signup" ? "signup" : "login"
  );

  // Form fields
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [hotelName, setHotelName] = useState("");
  const [hotelAddress, setHotelAddress] = useState("");
  const [phone, setPhone] = useState("");

  // States
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Password validation
  const hasLowercase = /[a-z]/.test(password);
  const hasUppercase = /[A-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSpecial = /[!@#$%^&*(),.?":{}|<>]/.test(password);
  const isValidPassword = password.length >= 8 && hasLowercase && hasUppercase && hasNumber && hasSpecial;

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      if (mode === "signup") {
        if (!isValidPassword) {
          throw new Error("Password does not meet requirements");
        }

        // Register new tenant
        const response = await authAPI.register({
          name: name,
          email: email,
          password: password,
          phone: phone || undefined,
          hotel_name: hotelName || undefined,
          hotel_address: hotelAddress || undefined,
        });

        // Store auth data
        setStoredAuth(response.access_token, response.refresh_token, response.tenant);
        setSuccess("Account created successfully!");
        setTimeout(() => router.push("/dashboard"), 1000);

      } else {
        // Login
        const response = await authAPI.login(email, password);
        setStoredAuth(response.access_token, response.refresh_token, response.tenant);
        router.push("/dashboard");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "An error occurred";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white text-black">
      <MarketingNav />
      <main className="relative mx-auto grid w-full max-w-7xl gap-px border border-black bg-black px-0 py-0 lg:grid-cols-2">
        {/* Left Panel - Branding */}
        <section className="bg-black p-8 text-white sm:p-12">
          <p className="mb-5 font-mono text-[10px] font-semibold uppercase tracking-[0.3em] text-white/55">
            Inika Bot // Access Layer
          </p>
          <h1 className="text-5xl font-black uppercase leading-[0.86] tracking-tighter sm:text-6xl lg:text-7xl">
            {mode === "signup" ? "Create Hotel Access" : "Operator Login"}
          </h1>
          <p className="mt-6 max-w-md text-[11px] uppercase leading-relaxed tracking-[0.18em] text-white/70">
            Tenant-isolated authentication for digital hotel operations. Sign in to control WhatsApp,
            journeys, booking sync, and knowledge systems.
          </p>

          <div className="mt-10 grid grid-cols-1 gap-px border border-white/30 bg-white/20 sm:grid-cols-2">
            <div className="bg-black px-5 py-4">
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-white/55">Environment</p>
              <p className="mt-2 text-sm font-black uppercase tracking-[0.08em]">Production Ready</p>
            </div>
            <div className="bg-black px-5 py-4">
              <p className="text-[10px] font-black uppercase tracking-[0.24em] text-white/55">Session Mode</p>
              <p className="mt-2 text-sm font-black uppercase tracking-[0.08em]">
                {mode === "signup" ? "Bootstrap" : "Authenticate"}
              </p>
            </div>
          </div>

          <div className="mt-6 border border-white/25 bg-white/5 p-4">
            <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.16em]">
              <ShieldCheck className="h-4 w-4" />
              <span className="text-white/90">System Status: Operational</span>
            </div>
            {getStoredTenant() && (
              <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.22em] text-white/60">
                Hotel: {getStoredTenant()?.hotel_name || getStoredTenant()?.name}
              </p>
            )}
          </div>
        </section>

        {/* Right Panel - Form */}
        <section className="bg-white p-8 text-black sm:p-12">
          <form onSubmit={onSubmit} className="space-y-6">
            <div>
              <p className="mb-3 text-[10px] font-black uppercase tracking-[0.28em] text-zinc-500">
                {mode === "signup" ? "Hotel Registration" : "Credential Input"}
              </p>
            </div>

            {/* Mode Toggle */}
            <div className="grid grid-cols-2 border border-black">
              <button
                type="button"
                onClick={() => { setMode("login"); setError(null); setSuccess(null); }}
                className={`py-3 text-[11px] font-black uppercase tracking-[0.2em] transition-colors ${
                  mode === "login" ? "bg-black text-white" : "bg-white text-black hover:bg-zinc-100"
                }`}
              >
                Login
              </button>
              <button
                type="button"
                onClick={() => { setMode("signup"); setError(null); setSuccess(null); }}
                className={`border-l border-black py-3 text-[11px] font-black uppercase tracking-[0.2em] transition-colors ${
                  mode === "signup" ? "bg-black text-white" : "bg-white text-black hover:bg-zinc-100"
                }`}
              >
                Sign Up
              </button>
            </div>

            {/* Signup-only fields */}
            {mode === "signup" && (
              <>
                <AxiomInput
                  label="Hotel/Admin Name"
                  value={name}
                  onChange={setName}
                  placeholder="John Smith"
                  autoComplete="name"
                  required
                  disabled={loading}
                />
                <AxiomInput
                  label="Hotel Name"
                  value={hotelName}
                  onChange={setHotelName}
                  placeholder="Hotel Paradise"
                  autoComplete="organization"
                  disabled={loading}
                />
                <AxiomInput
                  label="Hotel Address"
                  value={hotelAddress}
                  onChange={setHotelAddress}
                  placeholder="123 Beach Road, Miami"
                  autoComplete="street-address"
                  disabled={loading}
                />
                <AxiomInput
                  label="Phone (Optional)"
                  value={phone}
                  onChange={setPhone}
                  placeholder="+1234567890"
                  type="tel"
                  autoComplete="tel"
                  disabled={loading}
                />
              </>
            )}

            {/* Common fields */}
            <AxiomInput
              label="Email"
              value={email}
              onChange={setEmail}
              type="email"
              placeholder="admin@hotel.com"
              autoComplete="email"
              required
              disabled={loading}
            />
            <AxiomInput
              label="Password"
              value={password}
              onChange={setPassword}
              type="password"
              placeholder="••••••••"
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              required
              disabled={loading}
            />

            {/* Password requirements (signup only) */}
            {mode === "signup" && password.length > 0 && (
              <div className="border border-zinc-200 bg-zinc-50 p-3 space-y-1">
                <p className="text-[10px] font-black uppercase tracking-[0.12em] text-zinc-700 mb-2">
                  Password Requirements:
                </p>
                <div className="grid grid-cols-2 gap-1">
                  <div className={`flex items-center gap-1 text-[9px] font-mono ${hasLowercase ? 'text-green-600' : 'text-red-500'}`}>
                    {hasLowercase ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                    Lowercase letter
                  </div>
                  <div className={`flex items-center gap-1 text-[9px] font-mono ${hasUppercase ? 'text-green-600' : 'text-red-500'}`}>
                    {hasUppercase ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                    Uppercase letter
                  </div>
                  <div className={`flex items-center gap-1 text-[9px] font-mono ${hasNumber ? 'text-green-600' : 'text-red-500'}`}>
                    {hasNumber ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                    Number
                  </div>
                  <div className={`flex items-center gap-1 text-[9px] font-mono ${hasSpecial ? 'text-green-600' : 'text-red-500'}`}>
                    {hasSpecial ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                    Special character
                  </div>
                  <div className={`flex items-center gap-1 text-[9px] font-mono ${password.length >= 8 ? 'text-green-600' : 'text-red-500'}`}>
                    {password.length >= 8 ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                    Min 8 characters
                  </div>
                </div>
              </div>
            )}

            {/* Error message */}
            {error && (
              <div className="border border-red-500 bg-red-50 px-3 py-2 font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-red-700">
                {error}
              </div>
            )}

            {/* Success message */}
            {success && (
              <div className="border border-green-500 bg-green-50 px-3 py-2 font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-green-700">
                {success}
              </div>
            )}

            {/* Submit button */}
            <button
              type="submit"
              disabled={loading || (mode === "signup" && !isValidPassword)}
              className="flex w-full items-center justify-center gap-2 border border-black bg-black px-4 py-4 text-[11px] font-black uppercase tracking-[0.25em] text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {mode === "signup" ? "Creating Account..." : "Authenticating..."}
                </>
              ) : (
                <>
                  {mode === "signup" ? "Create Account" : "Sign In"}
                  <ChevronRight className="h-4 w-4" />
                </>
              )}
            </button>

            {/* Link to other mode */}
            <div className="border-t border-black pt-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-zinc-600">
                {mode === "signup" ? "Already have an account?" : "New to Inika Bot?"}{" "}
                <Link
                  href={mode === "signup" ? "/login" : "/login?mode=signup"}
                  className="font-black text-black hover:underline"
                >
                  {mode === "signup" ? "Switch to login" : "Create account"}
                </Link>
              </p>
            </div>
          </form>
        </section>
      </main>
    </div>
  );
}