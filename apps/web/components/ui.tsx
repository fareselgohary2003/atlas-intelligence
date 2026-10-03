import { AlertTriangle, Loader2 } from "lucide-react";
import { ReactNode } from "react";

export const STATUS: Record<string, { label: string; color: string; bg: string }> = {
  queued:        { label: "Queued",        color: "bg-slate-500",   bg: "bg-slate-500/10 text-slate-600 dark:text-slate-400" },
  paused:        { label: "Paused",        color: "bg-amber-500",   bg: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
  cancelled:     { label: "Cancelled",     color: "bg-zinc-500",    bg: "bg-zinc-500/10 text-zinc-600 dark:text-zinc-400" },
  planning:      { label: "Planning",      color: "bg-slate-400",   bg: "bg-slate-400/10 text-slate-600 dark:text-slate-400" },
  researching:   { label: "Researching",   color: "bg-indigo-500",  bg: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400" },
  verifying:     { label: "Verifying",     color: "bg-amber-500",   bg: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
  analyzing:     { label: "Analyzing",     color: "bg-violet-500",  bg: "bg-violet-500/10 text-violet-600 dark:text-violet-400" },
  completed:     { label: "Completed",     color: "bg-emerald-500", bg: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
  needs_review:  { label: "Needs review",  color: "bg-orange-500",  bg: "bg-orange-500/10 text-orange-600 dark:text-orange-400" },
  failed:        { label: "Failed",        color: "bg-red-500",     bg: "bg-red-500/10 text-red-600 dark:text-red-400" },
};

export const StatusDot = ({ s }: { s: string }) => {
  const st = STATUS[s];
  return (
    <span className={`inline-flex items-center gap-2 rounded-full px-2.5 py-0.5 text-xs font-medium ${st?.bg || "bg-bd text-mut"}`}>
      <span className={`h-2 w-2 rounded-full ${st?.color || "bg-bd"} ${s === "researching" ? "animate-pulse-glow" : ""}`} />
      {st?.label || s}
    </span>
  );
};

export const Mock = () => (
  <span className="rounded-md bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-amber-600 dark:text-amber-400 tracking-wider" title="Seeded demo data, not real research">
    MOCK
  </span>
);

export const Skeleton = ({ rows = 5 }: { rows?: number }) => (
  <div className="space-y-3 p-4" aria-busy>
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="h-6 rounded-lg skeleton-shimmer" style={{ animationDelay: `${i * 0.1}s`, width: `${85 - i * 8}%` }} />
    ))}
  </div>
);

export const ErrorBox = ({ msg, retry }: { msg: string; retry?: () => void }) => (
  <div className="flex items-center gap-3 rounded-lg border border-red-500/20 bg-red-500/5 p-4 text-red-600 dark:text-red-400 animate-fade-in">
    <AlertTriangle size={16} className="flex-shrink-0" />
    <span className="flex-1">{msg}</span>
    {retry && <button className="btn text-xs" onClick={retry}>Retry</button>}
  </div>
);

export const Card = ({ children, className = "", hover = false }: any) => (
  <div className={`rounded-xl border border-bd bg-card shadow-sm transition-all duration-200 ${hover ? "hover:shadow-md hover:-translate-y-0.5" : ""} ${className}`}>
    {children}
  </div>
);

export const Bar = ({ v }: { v: number }) => (
  <div className="flex items-center gap-2.5">
    <div className="h-1.5 w-24 rounded-full bg-bd overflow-hidden">
      <div
        className="h-1.5 rounded-full transition-all duration-500 ease-out"
        style={{
          width: v + "%",
          background: v >= 100 ? "var(--success)" : "linear-gradient(90deg, var(--acc), var(--acc-light))",
        }}
      />
    </div>
    <span className="font-mono text-[11px] text-mut tabular-nums">{v}%</span>
  </div>
);

const TONES: Record<string, string> = {
  ok:    "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  warn:  "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  bad:   "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400",
  info:  "border-indigo-500/30 bg-indigo-500/10 text-indigo-700 dark:text-indigo-400",
  muted: "border-bd bg-bg text-mut",
};

export const Pill = ({ tone = "muted", children }: { tone?: string; children: ReactNode }) => (
  <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold tracking-wide ${TONES[tone] || TONES.muted}`}>
    {children}
  </span>
);

export const Empty = ({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) => (
  <div className="py-16 text-center animate-fade-in">
    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-acc/10">
      <svg className="h-8 w-8 text-acc" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
      </svg>
    </div>
    <p className="text-base font-semibold">{title}</p>
    {hint && <p className="mx-auto mt-1 max-w-sm text-mut">{hint}</p>}
    {children && <div className="mt-4">{children}</div>}
  </div>
);

export const Gate = ({ q, children, rows = 4 }: { q: { data: any; error: string; loading: boolean; reload: () => void }; children: (d: any) => ReactNode; rows?: number }) =>
  q.error ? <ErrorBox msg={q.error} retry={q.reload} /> : q.loading || q.data == null ? <Skeleton rows={rows} /> : <>{children(q.data)}</>;

export const LoadingSpinner = ({ size = 16 }: { size?: number }) => (
  <Loader2 size={size} className="animate-spin text-acc" />
);
