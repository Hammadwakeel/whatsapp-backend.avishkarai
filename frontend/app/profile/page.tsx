"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { profileAPI, authAPI, clearStoredAuth, Tenant } from "@/lib/api";
import {
  User,
  LogOut,
  Code,
  ShieldCheck,
  Building2,
  MapPin,
  Phone,
  Mail,
  Loader2,
  Check,
  X,
} from "lucide-react";

export default function ProfilePage() {
  const router = useRouter();

  // Profile state
  const [profile, setProfile] = useState<Tenant | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Edit form state
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    phone: "",
    hotel_address: "",
  });

  // Password change state
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [passwordData, setPasswordData] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });

  // UI states
  const [isSaving, setIsSaving] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [message, setMessage] = useState({ text: "", type: "" });

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const data = await profileAPI.getProfile();
      setProfile(data);
      setFormData({
        name: data.name || "",
        phone: data.phone || "",
        hotel_address: data.hotel_address || "",
      });
    } catch {
      router.push("/login");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setMessage({ text: "", type: "" });

    try {
      const updated = await profileAPI.updateProfile(formData);
      setProfile(updated);
      setIsEditing(false);
      setMessage({ text: "Profile updated successfully", type: "success" });
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Update failed";
      setMessage({ text: msg, type: "error" });
    } finally {
      setIsSaving(false);
      setTimeout(() => setMessage({ text: "", type: "" }), 4000);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage({ text: "", type: "" });

    if (passwordData.new_password !== passwordData.confirm_password) {
      setMessage({ text: "Passwords do not match", type: "error" });
      return;
    }

    if (passwordData.new_password.length < 8) {
      setMessage({ text: "Password must be at least 8 characters", type: "error" });
      return;
    }

    setIsChangingPassword(true);

    try {
      await profileAPI.changePassword(
        passwordData.current_password,
        passwordData.new_password
      );
      setMessage({ text: "Password changed successfully", type: "success" });
      setShowPasswordForm(false);
      setPasswordData({ current_password: "", new_password: "", confirm_password: "" });
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Password change failed";
      setMessage({ text: msg, type: "error" });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleLogout = async () => {
    await authAPI.logout();
    router.push("/login");
  };

  const handleLogoutAll = async () => {
    if (confirm("This will log you out from all devices. Continue?")) {
      try {
        await authAPI.logoutAll();
        router.push("/login");
      } catch (error: unknown) {
        const msg = error instanceof Error ? error.message : "Logout failed";
        setMessage({ text: msg, type: "error" });
      }
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-black text-center font-mono text-white">
        <div className="mb-6 h-1 w-16 animate-pulse bg-white" />
        <p className="text-[10px] uppercase tracking-[0.4em] opacity-50">
          Decrypting_Operator_Profile...
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-white font-sans text-black selection:bg-black selection:text-white">
      {/* Header */}
      <header className="border-b border-black bg-white px-6 pb-20 pt-20 text-black">
        <div className="mx-auto max-w-7xl">
          <div className="mb-8 inline-flex items-center gap-2 text-black opacity-50">
            <Code className="h-4 w-4" />
            <span className="text-[10px] font-mono uppercase tracking-tighter">
              Operator Designation: ADMIN
            </span>
          </div>

          <h1 className="text-5xl font-black leading-[0.85] tracking-tighter md:text-[7rem]">
            SYSTEM <br />
            <span className="text-zinc-400">OPERATOR.</span>
          </h1>
        </div>
      </header>

      {/* Content */}
      <section className="bg-[#fcfcfc] px-6 py-20 pb-40">
        <div className="mx-auto max-w-7xl">
          {/* Section Title */}
          <div className="mb-12 flex items-center gap-4">
            <h2 className="whitespace-nowrap text-xs font-black uppercase tracking-[0.5em]">
              Identity Matrix
            </h2>
            <div className="h-px flex-grow bg-black" />
          </div>

          {/* Profile Grid */}
          <div className="mb-20 grid grid-cols-1 gap-px overflow-hidden border border-black bg-black md:grid-cols-12">
            {/* Left Panel - Profile Info */}
            <div className="flex flex-col items-center justify-center border-b border-black bg-white p-12 text-center transition hover:bg-zinc-50 md:col-span-4 md:border-b-0 md:border-r">
              <div className="mb-8 flex h-40 w-40 items-center justify-center border-2 border-black bg-zinc-100">
                <User className="h-16 w-16 text-zinc-400" />
              </div>

              <div className="w-full space-y-4">
                <div className="flex items-center justify-between border-b border-black pb-2">
                  <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-zinc-500">
                    Clearance
                  </span>
                  <span className="flex items-center gap-1 text-[10px] font-black uppercase">
                    <ShieldCheck className="h-3 w-3" /> Admin
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-black pb-2">
                  <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-zinc-500">
                    UID
                  </span>
                  <span className="text-[10px] font-mono uppercase text-zinc-400">
                    {profile?.id?.split("-")[0] || "UNKNOWN"}
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-black pb-2">
                  <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-zinc-500">
                    Status
                  </span>
                  <span className="flex items-center gap-1 text-[10px] font-black uppercase text-green-600">
                    <span className="h-2 w-2 rounded-full bg-green-600" /> Active
                  </span>
                </div>
              </div>
            </div>

            {/* Right Panel - Edit Form */}
            <div className="bg-white p-12 transition hover:bg-zinc-50 md:col-span-8">
              {/* Message Banner */}
              {message.text && (
                <div
                  className={`mb-10 flex items-center gap-3 border p-4 text-[10px] font-mono uppercase tracking-widest ${
                    message.type === "error"
                      ? "border-red-500 bg-red-500/10 text-red-600"
                      : "border-green-500 bg-green-500/10 text-green-600"
                  }`}
                >
                  <div
                    className={`h-2 w-2 rounded-full ${
                      message.type === "error" ? "bg-red-500" : "animate-pulse bg-green-600"
                    }`}
                  />
                  {message.text}
                </div>
              )}

              {/* Profile View or Edit Form */}
              {isEditing ? (
                <form onSubmit={handleSaveProfile} className="space-y-8">
                  <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
                    {/* Admin Name */}
                    <div>
                      <label className="mb-4 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-black">
                        <User className="h-3 w-3" /> Admin Name
                      </label>
                      <input
                        type="text"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="w-full rounded-none border-b border-black bg-transparent p-0 pb-4 text-xl font-bold text-black outline-none transition-colors focus:border-zinc-400"
                      />
                    </div>

                    {/* Phone */}
                    <div>
                      <label className="mb-4 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-black">
                        <Phone className="h-3 w-3" /> Phone
                      </label>
                      <input
                        type="tel"
                        value={formData.phone}
                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                        className="w-full rounded-none border-b border-black bg-transparent p-0 pb-4 text-xl font-bold text-black outline-none transition-colors focus:border-zinc-400"
                      />
                    </div>

                    {/* Hotel Address */}
                    <div className="md:col-span-2">
                      <label className="mb-4 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-black">
                        <MapPin className="h-3 w-3" /> Hotel Address
                      </label>
                      <input
                        type="text"
                        value={formData.hotel_address}
                        onChange={(e) => setFormData({ ...formData, hotel_address: e.target.value })}
                        className="w-full rounded-none border-b border-black bg-transparent p-0 pb-4 text-xl font-bold text-black outline-none transition-colors focus:border-zinc-400"
                      />
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex gap-4 pt-8">
                    <button
                      type="submit"
                      disabled={isSaving}
                      className="flex-1 border border-black bg-black p-4 text-xs font-black uppercase tracking-[0.3em] text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isSaving ? (
                        <span className="flex items-center justify-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin" /> Saving...
                        </span>
                      ) : (
                        "Commit Changes"
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setIsEditing(false);
                        setFormData({
                          name: profile?.name || "",
                          phone: profile?.phone || "",
                          hotel_address: profile?.hotel_address || "",
                        });
                      }}
                      className="border border-zinc-300 bg-white p-4 text-xs font-black uppercase tracking-[0.3em] transition hover:bg-zinc-100"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <div className="space-y-8">
                  {/* Static Info */}
                  <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
                    {/* Admin Name */}
                    <div>
                      <label className="mb-4 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500">
                        <User className="h-3 w-3" /> Admin Name
                      </label>
                      <p className="text-xl font-bold">{profile?.name || "Not set"}</p>
                    </div>

                    {/* Email */}
                    <div>
                      <label className="mb-4 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500">
                        <Mail className="h-3 w-3" /> Email
                      </label>
                      <p className="text-xl font-bold">{profile?.email || "Not set"}</p>
                    </div>

                    {/* Phone */}
                    <div>
                      <label className="mb-4 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500">
                        <Phone className="h-3 w-3" /> Phone
                      </label>
                      <p className="text-xl font-bold">{profile?.phone || "Not set"}</p>
                    </div>

                    {/* Hotel Name */}
                    <div>
                      <label className="mb-4 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500">
                        <Building2 className="h-3 w-3" /> Hotel Name
                      </label>
                      <p className="text-xl font-bold">{profile?.hotel_name || "Not set"}</p>
                    </div>

                    {/* Hotel Address */}
                    <div className="md:col-span-2">
                      <label className="mb-4 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500">
                        <MapPin className="h-3 w-3" /> Hotel Address
                      </label>
                      <p className="text-xl font-bold">{profile?.hotel_address || "Not set"}</p>
                    </div>
                  </div>

                  {/* Edit Button */}
                  <div className="pt-8">
                    <button
                      type="button"
                      onClick={() => setIsEditing(true)}
                      className="w-full border border-black bg-white p-6 text-xs font-black uppercase tracking-[0.3em] transition hover:bg-black hover:text-white"
                    >
                      Edit Profile
                    </button>
                  </div>
                </div>
              )}

              {/* Password Change Section */}
              <div className="mt-12 border-t border-zinc-200 pt-12">
                <button
                  type="button"
                  onClick={() => setShowPasswordForm(!showPasswordForm)}
                  className="mb-6 text-xs font-black uppercase tracking-widest text-zinc-500 hover:text-black"
                >
                  {showPasswordForm ? "- Hide Password Change" : "+ Change Password"}
                </button>

                {showPasswordForm && (
                  <form onSubmit={handleChangePassword} className="space-y-4">
                    <div>
                      <label className="mb-2 block text-[10px] font-black uppercase tracking-[0.2em]">
                        Current Password
                      </label>
                      <input
                        type="password"
                        value={passwordData.current_password}
                        onChange={(e) =>
                          setPasswordData({ ...passwordData, current_password: e.target.value })
                        }
                        className="input-field"
                        required
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-[10px] font-black uppercase tracking-[0.2em]">
                        New Password
                      </label>
                      <input
                        type="password"
                        value={passwordData.new_password}
                        onChange={(e) =>
                          setPasswordData({ ...passwordData, new_password: e.target.value })
                        }
                        className="input-field"
                        required
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-[10px] font-black uppercase tracking-[0.2em]">
                        Confirm New Password
                      </label>
                      <input
                        type="password"
                        value={passwordData.confirm_password}
                        onChange={(e) =>
                          setPasswordData({ ...passwordData, confirm_password: e.target.value })
                        }
                        className="input-field"
                        required
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={isChangingPassword}
                      className="border border-black bg-black p-4 text-xs font-black uppercase tracking-[0.3em] text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isChangingPassword ? (
                        <span className="flex items-center justify-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin" /> Changing...
                        </span>
                      ) : (
                        "Change Password"
                      )}
                    </button>
                  </form>
                )}
              </div>
            </div>
          </div>

          {/* Logout Section */}
          <div className="flex flex-col items-start justify-between gap-8 border border-black bg-white p-8 md:flex-row md:items-center md:p-12">
            <div>
              <h3 className="mb-2 text-xl font-black uppercase">Terminate Session</h3>
              <p className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
                Sever neural link and clear local token registry.
              </p>
            </div>
            <div className="flex gap-4 md:w-auto">
              <button
                type="button"
                onClick={handleLogoutAll}
                className="group flex items-center justify-center gap-4 border border-zinc-300 px-8 py-5 text-[10px] font-black uppercase tracking-[0.3em] transition hover:border-black hover:bg-zinc-100 md:w-auto"
              >
                Logout All Devices
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="group flex items-center justify-center gap-4 border border-black px-8 py-5 text-[10px] font-black uppercase tracking-[0.3em] transition hover:bg-black hover:text-white md:w-auto"
              >
                <LogOut className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
                Disconnect
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-900 bg-black px-6 py-12 text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between text-[10px] font-mono text-zinc-700">
          <div>// SECURE_CHANNEL_ACTIVE //</div>
          <div className="uppercase tracking-widest text-zinc-500">Identity Matrix Rendered</div>
        </div>
      </footer>
    </div>
  );
}