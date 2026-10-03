"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { Bot, ClipboardList, Database, FileText, FlaskConical, Gavel, LayoutDashboard, LogOut, Menu, Moon, Plus, Search, Settings, Sun, Link2, X, ChevronRight, Sparkles } from "lucide-react";
import { api } from "@/lib/api";

export type Ws = { id: string; name: string; role: string };
const Ctx = createContext<{ user: any; ws: Ws }>(null as any);
export const useSession = () => useContext(Ctx);
export const canWrite = (ws: Ws) => ["owner", "admin", "researcher"].includes(ws.role);
export const canAdmin = (ws: Ws) => ["owner", "admin"].includes(ws.role);

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/research", label: "Research", icon: FlaskConical },
  { href: "/evidence", label: "Evidence", icon: Database },
  { href: "/claims", label: "Claims", icon: Gavel },
  { href: "/sources", label: "Sources", icon: Link2 },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/audit", label: "Audit Log", icon: ClipboardList },
  { href: "/settings", label: "Settings", icon: Settings },
];

function Palette({ ws, close }: { ws: Ws; close: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  useEffect(() => {
    const t = setTimeout(() => api(`/api/research?workspace_id=${ws.id}&q=${encodeURIComponent(q)}&page_size=6`).then((r) => setHits(r.items)).catch(() => setHits([])), 150);
    return () => clearTimeout(t);
  }, [q, ws.id]);
  const go = (h: string) => { close(); router.push(h); };
  const pages = [...NAV.map((n) => ({ t: n.label, h: n.href, icon: n.icon })), { t: "Start new research", h: "/research/new", icon: Plus }];
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-20 backdrop-blur-sm animate-fade-in" onClick={close}>
      <div className="w-[580px] max-w-[92vw] overflow-hidden rounded-2xl border border-bd bg-card shadow-lg" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Command palette">
        <div className="flex items-center gap-3 border-b border-bd px-4">
          <Search size={16} className="text-mut" />
          <input autoFocus className="flex-1 bg-transparent py-3.5 outline-none placeholder:text-mut" placeholder="Search research projects or jump to a page…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Escape" && close()} />
          <kbd className="rounded-md border border-bd bg-bg px-1.5 py-0.5 font-mono text-[10px] text-mut">ESC</kbd>
        </div>
        <div className="max-h-80 overflow-auto p-2">
          {pages.filter((p) => p.t.toLowerCase().includes(q.toLowerCase())).map((p) => (
            <button key={p.h} onClick={() => go(p.h)} className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-bg group">
              <p.icon size={15} className="text-mut group-hover:text-acc transition-colors" />
              <span>{p.t}</span>
              <ChevronRight size={14} className="ml-auto text-mut opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          ))}
          {hits.length > 0 && <div className="my-1 border-t border-bd" />}
          {hits.map((r) => (
            <button key={r.id} onClick={() => go("/research/" + r.id)} className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-bg group">
              <FlaskConical size={15} className="text-mut group-hover:text-acc transition-colors" />
              <span className="flex-1 truncate">{r.title}</span>
              <span className="rounded-full bg-bg px-2 py-0.5 text-[11px] text-mut">{r.status}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Shell({ title, sub, actions, children }: { title: string; sub?: string; actions?: React.ReactNode; children: React.ReactNode }) {
  const router = useRouter(), path = usePathname();
  const [me, setMe] = useState<any>(null), [ws, setWs] = useState<Ws | null>(null), [authErr, setAuthErr] = useState("");
  const [dark, setDark] = useState(false), [drawer, setDrawer] = useState(false), [pal, setPal] = useState(false);

  useEffect(() => {
    api("/api/auth/me").then((u) => {
      setMe(u);
      const saved = localStorage.getItem("atlas_ws");  // UI preference only (which workspace is selected), not a credential
      setWs(u.workspaces.find((w: Ws) => w.id === saved) || u.workspaces[0]);
    }).catch((e) => setAuthErr(e.message));
    const d = localStorage.getItem("atlas_dark") === "1"; setDark(d); document.documentElement.classList.toggle("dark", d);
  }, []);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPal((p) => !p); } };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, []);

  if (authErr) return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-8 text-center">
        <p className="font-semibold text-red-600">Session Error</p>
        <p className="mt-1 text-sm text-mut">{authErr}</p>
        <Link href="/login" className="btn-p mt-4 inline-flex">Sign in again</Link>
      </div>
    </div>
  );
  if (!me || !ws) return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="h-10 w-10 rounded-xl bg-acc/20 animate-pulse" />
        <div className="h-3 w-32 rounded-full skeleton-shimmer" />
      </div>
    </div>
  );
  const toggle = () => { const d = !dark; setDark(d); localStorage.setItem("atlas_dark", d ? "1" : "0"); document.documentElement.classList.toggle("dark", d); };
  const logout = async () => { await api("/api/auth/logout", { method: "POST" }).catch(() => {}); router.replace("/login"); };

  return (
    <Ctx.Provider value={{ user: me, ws }}>
      <div className="flex min-h-screen">
        {/* Sidebar */}
        <aside className={`${drawer ? "flex" : "hidden"} fixed inset-y-0 z-40 w-60 flex-col bg-side text-slate-400 md:sticky md:top-0 md:flex md:h-screen`} aria-label="Primary">
          {/* Logo */}
          <div className="flex h-14 items-center gap-2.5 px-5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
              <Sparkles size={16} className="text-white" />
            </div>
            <span className="font-semibold tracking-wide text-white">ATLAS</span>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-0.5 px-3 mt-2">
            {NAV.map((n, i) => {
              const active = path.startsWith(n.href);
              return (
                <Link key={n.href} href={n.href} onClick={() => setDrawer(false)} aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-all duration-200 ${active ? "bg-white/10 text-white font-medium shadow-sm" : "hover:bg-white/5 hover:text-white"}`}
                  style={{ animationDelay: `${i * 30}ms` }}>
                  <n.icon size={16} className={active ? "text-acc-light" : ""} />
                  {n.label}
                  {active && <div className="ml-auto h-1.5 w-1.5 rounded-full bg-acc-light" />}
                </Link>
              );
            })}
          </nav>

          {/* Workspace selector & user */}
          <div className="space-y-3 border-t border-white/10 p-4">
            <select aria-label="Workspace" className="w-full rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-sm text-slate-300 transition-colors hover:bg-white/10" value={ws.id}
              onChange={(e) => { const w = me.workspaces.find((x: Ws) => x.id === e.target.value); localStorage.setItem("atlas_ws", w.id); setWs(w); router.refresh(); }}>
              {me.workspaces.map((w: Ws) => <option key={w.id} value={w.id} className="bg-side text-white">{w.name}</option>)}
            </select>
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 text-[11px] font-bold text-white">
                {me.name?.charAt(0)?.toUpperCase() || "?"}
              </div>
              <div className="flex-1 min-w-0">
                <p className="truncate text-xs font-medium text-slate-300">{me.name}</p>
                <p className="truncate text-[10px] text-slate-500">{ws.role}</p>
              </div>
              <button aria-label="Log out" onClick={logout} className="rounded-md p-1 text-slate-500 transition-colors hover:bg-white/5 hover:text-white">
                <LogOut size={14} />
              </button>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <div className="min-w-0 flex-1">
          {/* Header */}
          <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-bd glass px-4 md:px-6">
            <button className="md:hidden rounded-lg p-1.5 hover:bg-bg transition-colors" aria-label="Menu" onClick={() => setDrawer(!drawer)}>
              {drawer ? <X size={18} /> : <Menu size={18} />}
            </button>

            <button onClick={() => setPal(true)} className="flex w-72 max-w-full items-center gap-2 rounded-lg border border-bd bg-bg/50 px-3 py-1.5 text-mut transition-all hover:border-acc/30 hover:shadow-sm">
              <Search size={14} />
              <span className="text-sm">Search…</span>
              <kbd className="ml-auto rounded border border-bd bg-card px-1 py-0.5 font-mono text-[10px]">⌘K</kbd>
            </button>

            <div className="ml-auto flex items-center gap-2">
              <button className="btn text-xs" aria-label="Toggle theme" onClick={toggle}>
                {dark ? <Sun size={14} /> : <Moon size={14} />}
              </button>
              {canWrite(ws) && (
                <Link href="/research/new" className="btn-p text-sm">
                  <Plus size={14} />New research
                </Link>
              )}
            </div>
          </header>

          {/* Page content */}
          <main className="mx-auto max-w-7xl p-4 md:p-6 lg:p-8">
            <div className="mb-6 flex items-end justify-between animate-fade-in">
              <div>
                <h1 className="text-xl font-bold tracking-tight">{title}</h1>
                {sub && <p className="mt-0.5 text-sm text-mut">{sub}</p>}
              </div>
              {actions}
            </div>
            <div className="animate-fade-in" style={{ animationDelay: "100ms" }}>
              {children}
            </div>
          </main>
        </div>
      </div>
      {pal && <Palette ws={ws} close={() => setPal(false)} />}
    </Ctx.Provider>
  );
}
