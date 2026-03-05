"use client";

import { useState } from "react";
import { Loader2, AlertCircle, Eye, EyeOff } from "lucide-react";
import { usePanelStore } from "@/store/panelStore";
import { adminLogin } from "@/services/api";

export default function LoginCard() {
  const { login } = usePanelStore();
  const [uniqueId, setUniqueId] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [focused, setFocused] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uniqueId.trim() || !password.trim()) {
      setError("Both fields are required");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await adminLogin(uniqueId.trim(), password);
      login({
        id: res.admin.id,
        unique_id: res.admin.unique_id,
        name: res.admin.name,
        created_at: res.admin.created_at,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative w-full min-h-screen flex items-center justify-center overflow-hidden bg-black">
      {/* Animated background orbs */}
      <div className="absolute inset-0 overflow-hidden">
        <div
          className="absolute w-[500px] h-[500px] rounded-full opacity-[0.03] blur-[100px]"
          style={{
            background: "radial-gradient(circle, #ffffff 0%, transparent 70%)",
            top: "-10%",
            right: "-10%",
            animation: "float-slow 20s ease-in-out infinite",
          }}
        />
        <div
          className="absolute w-[400px] h-[400px] rounded-full opacity-[0.04] blur-[80px]"
          style={{
            background: "radial-gradient(circle, #22d3ee 0%, transparent 70%)",
            bottom: "-15%",
            left: "-5%",
            animation: "float-slow 25s ease-in-out infinite reverse",
          }}
        />
        <div
          className="absolute w-[300px] h-[300px] rounded-full opacity-[0.02] blur-[60px]"
          style={{
            background: "radial-gradient(circle, #a78bfa 0%, transparent 70%)",
            top: "40%",
            left: "60%",
            animation: "float-slow 18s ease-in-out infinite",
          }}
        />
      </div>

      {/* Grid pattern overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* Main card */}
      <div className="relative w-full max-w-[400px] mx-4 animate-fade-in">
        {/* Subtle glow behind card */}
        <div className="absolute -inset-px rounded-2xl bg-gradient-to-b from-white/[0.08] to-transparent" />

        <form
          onSubmit={handleSubmit}
          className="relative p-8 sm:p-10 rounded-2xl bg-[#0a0a0a]/90 backdrop-blur-xl border border-white/[0.06] shadow-[0_0_80px_rgba(0,0,0,0.8)]"
        >
          {/* Top accent line */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-24 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />

          {/* Branding */}
          <div className="flex flex-col items-center mb-8">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Admin
            </h1>
            <div className="w-8 h-px bg-white/15 mt-3 mb-2" />
            <p className="text-xs text-white/30 tracking-[0.2em] uppercase">
              Secure access
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2.5 px-4 py-3 mb-5 rounded-xl bg-red-500/8 border border-red-500/20 text-red-400 text-sm animate-slide-up">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Unique ID */}
          <div className="mb-4">
            <label
              className={`block text-[11px] mb-2 font-medium uppercase tracking-[0.15em] transition-colors duration-200 ${
                focused === "id" ? "text-white/60" : "text-white/25"
              }`}
            >
              Unique ID
            </label>
            <input
              type="text"
              value={uniqueId}
              onChange={(e) => setUniqueId(e.target.value)}
              onFocus={() => setFocused("id")}
              onBlur={() => setFocused(null)}
              placeholder="Enter your unique ID"
              autoFocus
              className="w-full px-4 py-3 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white text-sm placeholder:text-white/15 focus:bg-white/[0.06] focus:border-white/20 focus:outline-none transition-all duration-200"
            />
          </div>

          {/* Password */}
          <div className="mb-7">
            <label
              className={`block text-[11px] mb-2 font-medium uppercase tracking-[0.15em] transition-colors duration-200 ${
                focused === "pw" ? "text-white/60" : "text-white/25"
              }`}
            >
              Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={() => setFocused("pw")}
                onBlur={() => setFocused(null)}
                placeholder="Enter password"
                className="w-full px-4 py-3 pr-11 rounded-xl bg-white/[0.04] border border-white/[0.08] text-white text-sm placeholder:text-white/15 focus:bg-white/[0.06] focus:border-white/20 focus:outline-none transition-all duration-200"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-white/20 hover:text-white/50 transition-colors bg-transparent border-none p-1"
              >
                {showPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className={`relative w-full py-3 rounded-xl font-medium text-sm transition-all duration-300 flex items-center justify-center gap-2 overflow-hidden ${
              loading
                ? "bg-white/5 text-white/30 cursor-not-allowed border border-white/5"
                : "bg-white text-black border border-white/80 hover:bg-white/90 hover:shadow-[0_0_30px_rgba(255,255,255,0.1)] active:scale-[0.98]"
            }`}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Signing in…
              </>
            ) : (
              "Sign In"
            )}
          </button>

          {/* Bottom accent */}
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-16 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
        </form>

        {/* Footer text */}
        <p className="text-center text-[11px] text-white/15 mt-6 tracking-wide">
          BBFA Attendance System
        </p>
      </div>

      {/* CSS for floating animation */}
      <style jsx>{`
        @keyframes float-slow {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -30px) scale(1.05); }
          66% { transform: translate(-20px, 20px) scale(0.95); }
        }
      `}</style>
    </div>
  );
}
