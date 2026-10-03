"use client";
import Link from "next/link";
import ResearchTable from "@/components/ResearchTable";
import Shell, { useSession } from "@/components/Shell";
import { Card, Empty, Gate } from "@/components/ui";
import { useApi } from "@/lib/useApi";
import { formatCost, formatDuration, formatTokens, metric } from "@/lib/format.mjs";
import {
  Database,
  FileText,
  FlaskConical,
  Gavel,
  Bot,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Coins,
  Zap,
  TrendingUp,
  Activity,
  Sparkles,
  ArrowUpRight,
  PlusCircle,
  Compass,
  CheckCircle2,
  Share2,
  PieChart as PieIcon,
  BarChart3,
  Layers,
  Network,
} from "lucide-react";

const TILE_ICONS: Record<string, any> = {
  "Research projects": FlaskConical,
  "Active research": Activity,
  "Completed research": TrendingUp,
  "Sources": Database,
  "Evidence items": FileText,
  "Claims": Gavel,
  "Verified claims": ShieldCheck,
  "Conflicts": AlertTriangle,
  "Agent runs": Bot,
  "Avg. research duration": Clock,
  "LLM calls": Zap,
  "Estimated cost": Coins,
};

const TILE_LINKS: Record<string, string> = {
  "Research projects": "/research",
  "Active research": "/research",
  "Completed research": "/research",
  "Sources": "/sources",
  "Evidence items": "/evidence",
  "Claims": "/claims",
  "Verified claims": "/claims",
  "Conflicts": "/claims",
  "Agent runs": "/agents",
  "Avg. research duration": "/research",
  "LLM calls": "/settings",
  "Estimated cost": "/settings",
};

const TILE_GRADIENTS: Record<string, string> = {
  "Research projects": "from-indigo-500/20 to-indigo-500/5 text-indigo-600 dark:text-indigo-400 border-indigo-500/20",
  "Active research": "from-blue-500/20 to-blue-500/5 text-blue-600 dark:text-blue-400 border-blue-500/20",
  "Completed research": "from-emerald-500/20 to-emerald-500/5 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  "Sources": "from-cyan-500/20 to-cyan-500/5 text-cyan-600 dark:text-cyan-400 border-cyan-500/20",
  "Evidence items": "from-violet-500/20 to-violet-500/5 text-violet-600 dark:text-violet-400 border-violet-500/20",
  "Claims": "from-amber-500/20 to-amber-500/5 text-amber-600 dark:text-amber-400 border-amber-500/20",
  "Verified claims": "from-green-500/20 to-green-500/5 text-green-600 dark:text-green-400 border-green-500/20",
  "Conflicts": "from-orange-500/20 to-orange-500/5 text-orange-600 dark:text-orange-400 border-orange-500/20",
  "Agent runs": "from-purple-500/20 to-purple-500/5 text-purple-600 dark:text-purple-400 border-purple-500/20",
  "Avg. research duration": "from-slate-500/20 to-slate-500/5 text-slate-600 dark:text-slate-400 border-slate-500/20",
  "LLM calls": "from-rose-500/20 to-rose-500/5 text-rose-600 dark:text-rose-400 border-rose-500/20",
  "Estimated cost": "from-teal-500/20 to-teal-500/5 text-teal-600 dark:text-teal-400 border-teal-500/20",
};

function MetricTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  const none = value === "No data yet" || value === "Unavailable";
  const Icon = TILE_ICONS[label] || FlaskConical;
  const href = TILE_LINKS[label] || "/research";
  const gradientStyle = TILE_GRADIENTS[label] || "from-indigo-500/20 to-indigo-500/5 text-indigo-500 border-indigo-500/20";

  return (
    <Link href={href} className="block group">
      <Card className="relative overflow-hidden p-4 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:border-primary/50 cursor-pointer">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold text-mut tracking-tight truncate group-hover:text-primary transition-colors">
              {label}
            </div>
            <div className={`mt-1.5 font-mono tracking-tight tabular-nums ${none ? "text-sm text-mut" : "text-2xl font-extrabold text-tx"}`}>
              {value}
            </div>
            {sub && <div className="mt-1 text-[11px] font-medium text-mut truncate">{sub}</div>}
          </div>
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border bg-gradient-to-br ${gradientStyle} shadow-sm transition-transform duration-300 group-hover:scale-110`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </Card>
    </Link>
  );
}

function Body() {
  const { ws, user } = useSession();
  const s = useApi<any>(`/api/research/summary?workspace_id=${ws?.id}`);
  const audit = useApi<any>(`/api/workspaces/${ws?.id}/audit?limit=8`);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/15 via-primary/5 to-transparent p-6 shadow-sm backdrop-blur-md">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-0.5 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Atlas Multi-Agent Deep Research Engine</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-tx">
              Welcome back, {user?.name || "Fares Elgohary"}! 👋
            </h1>
            <p className="text-sm text-mut max-w-xl">
              Turn complex enterprise and market questions into verified evidence graphs, multi-source fact checking, and executive reports.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/research/new"
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-primary to-accent px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-primary/25 transition-all duration-200 hover:shadow-lg hover:shadow-primary/40 hover:brightness-110 active:scale-95"
            >
              <PlusCircle className="h-4 w-4" />
              <span>New Deep Research</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Metrics Section */}
      <div>
        <div className="mb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              <h2 className="text-base font-bold text-tx tracking-tight">Workspace-Wide Aggregate Metrics</h2>
            </div>
            <p className="text-xs text-mut mt-0.5">
              Aggregated across all research projects in the current workspace.
            </p>
          </div>
          <span className="text-xs text-mut flex items-center gap-1.5 shrink-0">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            Live synchronized across all projects · Click any card to explore
          </span>
        </div>

        <Gate q={s} rows={3}>
          {(m) =>
            m.total === 0 ? (
              <Card className="p-8 text-center border-dashed border-2">
                <Empty
                  title="No research runs yet"
                  hint="Launch your first deep research brief to unlock automated multi-agent fact synthesis, claim verification, and conflict detection."
                >
                  <Link href="/research/new" className="btn-p mt-4">
                    <PlusCircle className="h-4 w-4" />
                    Start First Research Brief
                  </Link>
                </Empty>
              </Card>
            ) : (
              <>
                {m.demo_projects > 0 && (
                  <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-700 dark:text-amber-300 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-amber-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold">SEEDED / DEMO DATA INCLUDED</span>
                      <span>
                        Workspace includes <strong>{m.demo_projects}</strong> demo project{m.demo_projects > 1 ? "s" : ""} ({m.demo_claims || 0} synthetic claim{m.demo_claims === 1 ? "" : "s"}).
                      </span>
                    </div>
                    <span className="text-[11px] text-mut">Metrics below represent workspace-wide aggregate totals</span>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
                  <MetricTile label="Research projects" value={metric(m.total)} />
                  <MetricTile label="Active research" value={metric(m.active)} />
                  <MetricTile label="Completed research" value={metric(m.completed)} />
                  <MetricTile label="Sources" value={metric(m.sources)} />
                  <MetricTile label="Evidence items" value={metric(m.evidence)} />
                  <MetricTile label="Claims" value={metric(m.claims)} />
                  <MetricTile label="Verified claims" value={metric(m.verified_claims)} />
                  <MetricTile label="Conflicts" value={metric(m.conflicts)} />
                  <MetricTile label="Agent runs" value={metric(m.agent_runs)} />
                  <MetricTile label="Avg. research duration" value={formatDuration(m.avg_duration_seconds)} />
                  <MetricTile
                    label="LLM calls"
                    value={metric(m.usage.calls)}
                    sub={`${formatTokens(m.usage.input_tokens + m.usage.output_tokens, m.usage.input_tokens + m.usage.output_tokens > 0)} tokens`}
                  />
                  <MetricTile
                    label="Estimated cost"
                    value={formatCost(m.usage.estimated_cost, m.usage.calls_with_cost === m.usage.calls)}
                    sub={m.usage.estimated_cost == null ? "Prices not configured" : undefined}
                  />
                </div>

                {/* Visual Analytics & Graphs Panel */}
                <div className="mt-6 grid gap-4 lg:grid-cols-3">
                  {/* Visual Breakdown 1: Evidence & Claims Pipeline */}
                  <Link href="/evidence" className="block group">
                    <Card className="p-5 border-bd shadow-sm hover:border-primary/50 transition-all duration-300 hover:-translate-y-1 h-full">
                      <div className="flex items-center justify-between pb-3 border-b border-bd/60">
                        <div className="flex items-center gap-2">
                          <Layers className="h-4 w-4 text-primary" />
                          <h3 className="text-xs font-bold uppercase tracking-wider text-tx group-hover:text-primary transition-colors">
                            Evidence Pipeline
                          </h3>
                        </div>
                        <span className="text-[11px] font-semibold text-primary flex items-center gap-1">
                          View details <ArrowUpRight className="h-3 w-3" />
                        </span>
                      </div>
                      <div className="mt-4 space-y-3">
                        <div>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-mut">Sources Harvested</span>
                            <span className="font-mono font-bold text-tx">{m.sources}</span>
                          </div>
                          <div className="h-2 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500"
                              style={{ width: `${Math.min(100, (m.sources / Math.max(m.sources + m.evidence, 1)) * 100)}%` }}
                            />
                          </div>
                        </div>

                        <div>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-mut">Extracted Evidence Snippets</span>
                            <span className="font-mono font-bold text-tx">{m.evidence}</span>
                          </div>
                          <div className="h-2 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-primary transition-all duration-500"
                              style={{ width: `${Math.min(100, (m.evidence / Math.max(m.evidence + m.claims, 1)) * 100)}%` }}
                            />
                          </div>
                        </div>

                        <div>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-mut">Synthesized Claims</span>
                            <span className="font-mono font-bold text-tx">{m.claims}</span>
                          </div>
                          <div className="h-2 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all duration-500"
                              style={{ width: `${Math.min(100, (m.claims / Math.max(m.claims + 5, 1)) * 100)}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </Card>
                  </Link>

                  {/* Visual Breakdown 2: Multi-Agent Execution */}
                  <Link href="/agents" className="block group">
                    <Card className="p-5 border-bd shadow-sm hover:border-primary/50 transition-all duration-300 hover:-translate-y-1 h-full flex flex-col justify-between">
                      <div>
                        <div className="flex items-center justify-between pb-3 border-b border-bd/60">
                          <div className="flex items-center gap-2">
                            <Bot className="h-4 w-4 text-primary" />
                            <h3 className="text-xs font-bold uppercase tracking-wider text-tx group-hover:text-primary transition-colors">
                              Multi-Agent Execution
                            </h3>
                          </div>
                          <span className="text-[11px] font-semibold text-emerald-500 flex items-center gap-1">
                            Live Agents <ArrowUpRight className="h-3 w-3" />
                          </span>
                        </div>
                        <div className="mt-4 flex items-center justify-around py-2">
                          <div className="text-center">
                            <div className="flex h-12 w-12 mx-auto items-center justify-center rounded-2xl bg-primary/10 text-primary font-mono text-lg font-extrabold border border-primary/20 shadow-sm">
                              {m.agent_runs}
                            </div>
                            <div className="mt-2 text-[11px] font-semibold text-mut">Agent Runs</div>
                          </div>
                          <div className="h-10 w-px bg-bd/60" />
                          <div className="text-center">
                            <div className="flex h-12 w-12 mx-auto items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500 font-mono text-lg font-extrabold border border-amber-500/20 shadow-sm">
                              {m.conflicts}
                            </div>
                            <div className="mt-2 text-[11px] font-semibold text-mut">Conflicts Flagged</div>
                          </div>
                          <div className="h-10 w-px bg-bd/60" />
                          <div className="text-center">
                            <div className="flex h-12 w-12 mx-auto items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-500 font-mono text-lg font-extrabold border border-emerald-500/20 shadow-sm">
                              {m.completed}
                            </div>
                            <div className="mt-2 text-[11px] font-semibold text-mut">Completed</div>
                          </div>
                        </div>
                      </div>
                      <div className="pt-2 text-center text-[11px] text-mut font-medium">
                        Click to view individual agent traces & status
                      </div>
                    </Card>
                  </Link>

                  {/* Visual Breakdown 3: Knowledge Graph Quick Launch */}
                  <Link href="/claims" className="block group">
                    <Card className="p-5 border-bd shadow-sm hover:border-primary/50 transition-all duration-300 hover:-translate-y-1 h-full flex flex-col justify-between bg-gradient-to-br from-surface to-primary/5">
                      <div>
                        <div className="flex items-center justify-between pb-2 border-b border-bd/60">
                          <div className="flex items-center gap-2">
                            <Network className="h-4 w-4 text-primary" />
                            <h3 className="text-xs font-bold uppercase tracking-wider text-tx group-hover:text-primary transition-colors">
                              Knowledge Graph Linkage
                            </h3>
                          </div>
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                            Explore Linkage
                          </span>
                        </div>
                        <p className="mt-3 text-xs leading-relaxed text-mut">
                          Interactive node linkage maps claims directly to citation URLs, resolving market contradictions with visual confidence scores.
                        </p>
                      </div>
                      <div className="mt-4 pt-3 border-t border-bd/40 flex items-center justify-between text-xs font-semibold text-primary">
                        <span>View claims & evidence network</span>
                        <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                      </div>
                    </Card>
                  </Link>
                </div>
              </>
            )
          }
        </Gate>
      </div>

      {/* Projects Table Section */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Compass className="h-4 w-4 text-primary" />
            <h2 className="text-base font-bold text-tx tracking-tight">Active Research Briefs</h2>
          </div>
          <Link
            href="/research"
            className="group flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
          >
            <span>View all briefs</span>
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </Link>
        </div>
        <ResearchTable compact />
      </div>

      {/* Audit Activity Section */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <h2 className="text-base font-bold text-tx tracking-tight">Workspace Audit Timeline</h2>
          </div>
          <Link href="/audit" className="text-xs text-primary font-semibold hover:underline flex items-center gap-1">
            <span>View full audit log</span>
            <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
        <Card className="overflow-hidden border-bd shadow-sm">
          <Gate q={audit} rows={3}>
            {(a) =>
              a.items.length === 0 ? (
                <p className="p-8 text-center text-sm text-mut">No activity events recorded yet.</p>
              ) : (
                <div className="divide-y divide-bd">
                  {a.items.map((x: any, i: number) => (
                    <Link
                      key={x.id}
                      href="/audit"
                      className="flex items-center gap-3.5 px-5 py-3.5 transition-colors hover:bg-primary/5 group"
                      style={{ animationDelay: `${i * 40}ms` }}
                    >
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary group-hover:scale-110 transition-transform">
                        <Activity className="h-4 w-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-semibold text-tx uppercase tracking-wider group-hover:text-primary transition-colors">
                            {x.action.replace(/_/g, " ")}
                          </span>
                          {x.actor && (
                            <span className="text-xs text-mut">
                              by <strong className="text-tx/90 font-medium">{x.actor}</strong>
                            </span>
                          )}
                        </div>
                      </div>
                      <span className="shrink-0 font-mono text-[11px] text-mut tabular-nums">
                        {x.created_at.slice(0, 16).replace("T", " ")}
                      </span>
                    </Link>
                  ))}
                </div>
              )
            }
          </Gate>
        </Card>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Shell title="Intelligence Dashboard" sub="Real-time multi-agent research and analysis workspace">
      <Body />
    </Shell>
  );
}
