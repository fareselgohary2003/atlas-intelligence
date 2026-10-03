"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Eye, EyeOff, Sparkles } from "lucide-react";

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [f, setF] = useState({ email: "", password: "", name: "", workspace_name: "" });
  const [err, setErr] = useState(""), [busy, setBusy] = useState(false), [showPw, setShowPw] = useState(false);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      await api(`/api/auth/${mode}`, { method: "POST", body: JSON.stringify(mode === "login" ? { email: f.email, password: f.password } : f) });
      router.replace("/dashboard");  // the server set httpOnly session + CSRF cookies; nothing is stored in JavaScript
    } catch (x: any) { setErr(x.message); setBusy(false); }
  };
  return (
    <div className="grid min-h-screen md:grid-cols-2">
      {/* Left panel - branding */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-side p-10 text-slate-300 md:flex">
        {/* Background gradient decoration */}
        <div className="absolute -top-40 -left-40 h-80 w-80 rounded-full bg-indigo-600/20 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 h-80 w-80 rounded-full bg-violet-600/20 blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-60 w-60 rounded-full bg-indigo-500/10 blur-2xl" />

        <div className="relative z-10 flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/25">
            <Sparkles size={18} className="text-white" />
          </div>
          <span className="text-lg font-semibold tracking-wide text-white">ATLAS</span>
        </div>

        <div className="relative z-10 max-w-md">
          <h2 className="text-3xl font-bold leading-tight text-white">
            Turn complex business questions into evidence-backed intelligence.
          </h2>
          <p className="mt-4 text-base leading-relaxed text-slate-400">
            An autonomous research and intelligence platform for strategy, investment and product teams.
            Powered by specialised AI agents that search, verify, and synthesise real sources.
          </p>

          {/* Feature highlights */}
          <div className="mt-8 grid grid-cols-2 gap-4">
            {[
              { n: "9", label: "Specialised agents" },
              { n: "100%", label: "Source-grounded" },
              { n: "Auto", label: "Fact verification" },
              { n: "Full", label: "Audit trail" },
            ].map((f) => (
              <div key={f.label} className="rounded-xl border border-white/10 bg-white/5 p-3 backdrop-blur">
                <p className="text-lg font-bold text-white">{f.n}</p>
                <p className="text-xs text-slate-400">{f.label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10 text-xs text-slate-600">Atlas Intelligence Platform</div>
      </div>

      {/* Right panel - form */}
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-4 animate-fade-in">
          {/* Mobile logo */}
          <div className="mb-6 flex items-center gap-2 md:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
              <Sparkles size={14} className="text-white" />
            </div>
            <span className="font-semibold tracking-wide">ATLAS</span>
          </div>

          <div>
            <h1 className="text-2xl font-bold tracking-tight">{mode === "login" ? "Welcome back" : "Create your workspace"}</h1>
            <p className="mt-1 text-sm text-mut">{mode === "login" ? "Sign in to your Atlas account" : "Get started with Atlas Intelligence"}</p>
          </div>

          {mode === "signup" && (
            <>
              <div>
                <label className="mb-1 block text-xs font-medium text-mut">Your name</label>
                <input className="inp" placeholder="John Doe" required value={f.name} onChange={set("name")} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-mut">Workspace name</label>
                <input className="inp" placeholder="Acme Research" required value={f.workspace_name} onChange={set("workspace_name")} />
              </div>
            </>
          )}

          <div>
            <label className="mb-1 block text-xs font-medium text-mut">Email</label>
            <input className="inp" type="email" placeholder="you@company.com" required autoComplete="username" value={f.email} onChange={set("email")} />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-mut">Password</label>
            <div className="relative">
              <input className="inp pr-10" type={showPw ? "text" : "password"} placeholder={mode === "signup" ? "8+ characters" : "••••••••"} required
                autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "signup" ? 8 : 1} value={f.password} onChange={set("password")} />
              <button type="button" className="absolute right-2.5 top-1/2 -translate-y-1/2 text-mut hover:text-tx transition-colors" onClick={() => setShowPw(!showPw)} tabIndex={-1}>
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {err && (
            <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-600 dark:text-red-400 animate-fade-in" role="alert">
              {err}
            </div>
          )}

          <button className="btn-p w-full justify-center text-sm" disabled={busy}>
            {busy ? (
              <><span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />Working…</>
            ) : mode === "login" ? "Sign in" : "Create account"}
          </button>

          <p className="text-center text-sm text-mut">
            {mode === "login" ? (
              <>Don&apos;t have an account? <Link className="font-medium text-acc hover:underline" href="/signup">Create one</Link></>
            ) : (
              <>Already have an account? <Link className="font-medium text-acc hover:underline" href="/login">Sign in</Link></>
            )}
          </p>
        </form>
      </div>
    </div>
  );
}
