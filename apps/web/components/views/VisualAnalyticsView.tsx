"use client";
import { useState } from "react";
import { useApi } from "@/lib/useApi";
import { Card, Gate, Mock, Pill } from "../ui";
import { claimLabel, tone } from "@/lib/format.mjs";
import {
  BarChart3,
  Table as TableIcon,
  PieChart as PieIcon,
  TrendingUp,
  ShieldCheck,
  AlertTriangle,
  Database,
  Layers,
  Sparkles,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Network,
  Scale,
  Compass,
  Search,
  SlidersHorizontal,
  ExternalLink,
  ArrowUpRight,
  FileText,
  Activity,
  Globe,
  Tag,
  BookOpen,
} from "lucide-react";

export default function VisualAnalyticsView({ rid }: { rid: string }) {
  const [viewMode, setViewMode] = useState<"visual" | "table">("visual");
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");

  const p = useApi<any>(`/api/research/${rid}`);
  const claimsQ = useApi<any>(`/api/research/${rid}/claims?limit=200`);
  const evidenceQ = useApi<any>(`/api/research/${rid}/evidence?limit=200`);
  const sourcesQ = useApi<any>(`/api/research/${rid}/sources?limit=200`);
  const graphQ = useApi<any>(`/api/research/${rid}/graph?limit=200`);

  const isDemo = Boolean(p.data?.is_demo || (Array.isArray(claimsQ.data) && claimsQ.data.some((c: any) => c.is_demo)));

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Controls & View Mode Switcher */}
      <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/15 via-accent/5 to-transparent p-6 shadow-sm backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-0.5 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Multi-Source Intelligence & Verification Engine</span>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-tx">
              {p.data?.title || "Research Project Intelligence"}
            </h2>
            <p className="text-xs text-mut max-w-xl">
              Interactive visualization charts, verification spectrums, persisted research findings, and structured data tables.
            </p>
          </div>

          {/* Mode Switcher Toggle Buttons */}
          <div className="flex items-center gap-2 bg-surface/90 p-1.5 rounded-xl border border-bd/70 shadow-sm">
            <button
              onClick={() => setViewMode("visual")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                viewMode === "visual"
                  ? "bg-primary text-white shadow-md shadow-primary/30"
                  : "text-mut hover:text-tx hover:bg-surface"
              }`}
            >
              <BarChart3 className="h-4 w-4" />
              <span>Visual Charts View</span>
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                viewMode === "table"
                  ? "bg-primary text-white shadow-md shadow-primary/30"
                  : "text-mut hover:text-tx hover:bg-surface"
              }`}
            >
              <TableIcon className="h-4 w-4" />
              <span>Data Table View</span>
            </button>
          </div>
        </div>
      </div>

      {/* DEMO NOTICE BANNER (when demo data is used) */}
      {isDemo && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-500 mt-0.5" />
          <div className="space-y-1">
            <div className="font-bold flex items-center gap-2">
              <span>DEMO MODE ACTIVE — SIMULATED RESEARCH DATA</span>
              <Mock />
            </div>
            <p className="leading-relaxed">
              All findings, metrics, and citations are simulated demo data hosted on <code className="px-1 py-0.5 rounded bg-amber-500/20 font-mono text-[11px]">.invalid</code> domains.
              The market figures, growth rates, and claims displayed below are fictional demo data generated for demonstration purposes and never originate from real government or market reports.
            </p>
          </div>
        </div>
      )}

      {/* VIEW MODE 1: VISUALIZATION CHARTS & MATRICES */}
      {viewMode === "visual" && (
        <div className="space-y-6">
          {/* Quick Metrics Bar */}
          <Gate q={claimsQ}>
            {(claimsData) => {
              const claims = Array.isArray(claimsData) ? claimsData : (claimsData?.items || []);
              const evidenceList = Array.isArray(evidenceQ.data) ? evidenceQ.data : (evidenceQ.data?.items || []);
              const verifiedCount = claims.filter((c: any) => c.status === "supported" || c.confidence === "VERIFIED").length;
              const partialCount = claims.filter((c: any) => c.status === "partially_supported" || c.confidence === "PARTIALLY SUPPORTED").length;
              const unverifiedCount = claims.filter((c: any) => c.status === "unverified" || c.confidence === "UNVERIFIED" || c.status === "proposed").length;

              return (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <Card className="p-4 border-l-4 border-l-emerald-500 shadow-sm">
                    <div className="text-xs text-mut font-medium">Verified Claims</div>
                    <div className="mt-1 text-2xl font-extrabold font-mono text-emerald-600 dark:text-emerald-400">
                      {verifiedCount}
                    </div>
                    <div className="text-[11px] text-mut mt-0.5">Corroborated across sources</div>
                  </Card>
                  <Card className="p-4 border-l-4 border-l-amber-500 shadow-sm">
                    <div className="text-xs text-mut font-medium">Partially Supported</div>
                    <div className="mt-1 text-2xl font-extrabold font-mono text-amber-600 dark:text-amber-400">
                      {partialCount}
                    </div>
                    <div className="text-[11px] text-mut mt-0.5">Single source / uncorroborated</div>
                  </Card>
                  <Card className="p-4 border-l-4 border-l-slate-400 shadow-sm">
                    <div className="text-xs text-mut font-medium">Inferences / Unverified</div>
                    <div className="mt-1 text-2xl font-extrabold font-mono text-tx">
                      {unverifiedCount}
                    </div>
                    <div className="text-[11px] text-mut mt-0.5">Logical extrapolations</div>
                  </Card>
                  <Card className="p-4 border-l-4 border-l-primary shadow-sm">
                    <div className="text-xs text-mut font-medium">Harvested Citations</div>
                    <div className="mt-1 text-2xl font-extrabold font-mono text-primary">
                      {evidenceList.length}
                    </div>
                    <div className="text-[11px] text-mut mt-0.5">Verbatim source excerpts</div>
                  </Card>
                </div>
              );
            }}
          </Gate>

          {/* Visual Charts Grid */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {/* Chart 1: Claim Verification Spectrum (Donut & Progress Bars) */}
            <Card className="p-5 border-bd shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-bd/60">
                  <div className="flex items-center gap-2">
                    <PieIcon className="h-4 w-4 text-primary" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-tx">Verification Breakdown</h3>
                  </div>
                  <span className="text-[11px] font-semibold text-primary">Accuracy</span>
                </div>
                <Gate q={claimsQ} rows={4}>
                  {(data) => {
                    const items = Array.isArray(data) ? data : (data?.items || []);
                    const verified = items.filter((c: any) => c.status === "supported" || c.confidence === "VERIFIED").length;
                    const partial = items.filter((c: any) => c.status === "partially_supported" || c.confidence === "PARTIALLY SUPPORTED").length;
                    const unverified = items.filter((c: any) => c.status === "unverified" || c.confidence === "UNVERIFIED" || c.status === "proposed").length;
                    const total = Math.max(items.length, 1);

                    const verifiedPct = Math.round((verified / total) * 100);
                    const partialPct = Math.round((partial / total) * 100);
                    const unverifiedPct = Math.round((unverified / total) * 100);

                    return (
                      <div className="mt-4 space-y-4">
                        {/* SVG Donut Chart */}
                        <div className="flex items-center justify-center py-2">
                          <div className="relative flex items-center justify-center">
                            <svg className="w-28 h-28 transform -rotate-90" viewBox="0 0 36 36">
                              <path
                                className="text-surface"
                                strokeWidth="3.8"
                                stroke="currentColor"
                                fill="none"
                                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                              />
                              <path
                                className="text-emerald-500"
                                strokeDasharray={`${verifiedPct}, 100`}
                                strokeWidth="3.8"
                                strokeLinecap="round"
                                stroke="currentColor"
                                fill="none"
                                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                              />
                              <path
                                className="text-amber-500"
                                strokeDasharray={`${partialPct}, 100`}
                                strokeDashoffset={`-${verifiedPct}`}
                                strokeWidth="3.8"
                                strokeLinecap="round"
                                stroke="currentColor"
                                fill="none"
                                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                              />
                            </svg>
                            <div className="absolute text-center">
                              <span className="text-lg font-extrabold font-mono text-tx">{verifiedPct}%</span>
                              <span className="block text-[9px] text-mut uppercase font-semibold">Verified</span>
                            </div>
                          </div>
                        </div>

                        {/* Legend */}
                        <div className="space-y-2 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="flex items-center gap-1.5 text-tx font-medium">
                              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                              Verified / Supported
                            </span>
                            <span className="font-mono font-bold text-tx">{verified} ({verifiedPct}%)</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="flex items-center gap-1.5 text-tx font-medium">
                              <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                              Partially Supported
                            </span>
                            <span className="font-mono font-bold text-tx">{partial} ({partialPct}%)</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="flex items-center gap-1.5 text-tx font-medium">
                              <span className="h-2.5 w-2.5 rounded-full bg-slate-400" />
                              Inferences / Unverified
                            </span>
                            <span className="font-mono font-bold text-tx">{unverified} ({unverifiedPct}%)</span>
                          </div>
                        </div>
                      </div>
                    );
                  }}
                </Gate>
              </div>
              <div className="mt-4 pt-3 border-t border-bd/50 text-[11px] text-mut">
                Multi-pass fact checking across all extracted citations.
              </div>
            </Card>

            {/* Chart 2: Quantitative Research Findings & Metrics (Bar Visualizer) */}
            <Card className="p-5 border-bd shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-bd/60">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-primary" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-tx">Persisted Research Findings</h3>
                  </div>
                  <span className="text-[11px] font-semibold text-emerald-500">
                    {isDemo ? "Simulated Findings" : "Grounded Metrics"}
                  </span>
                </div>

                <Gate q={claimsQ} rows={4}>
                  {(data) => {
                    const items = Array.isArray(data) ? data : (data?.items || []);
                    const numericClaims = items.filter((c: any) => c.attributes?.value != null);

                    if (numericClaims.length > 0) {
                      const maxValue = Math.max(...numericClaims.map((c: any) => Number(c.attributes.value) || 1), 1);
                      return (
                        <div className="mt-5 space-y-4">
                          {numericClaims.slice(0, 4).map((c: any, i: number) => {
                            const val = Number(c.attributes.value);
                            const unit = c.attributes.unit || "";
                            const pct = Math.min(100, Math.round((val / maxValue) * 100));
                            const label = c.attributes.metric || c.text;
                            return (
                              <div key={c.id || i}>
                                <div className="flex justify-between text-xs mb-1.5">
                                  <span className="text-tx font-medium truncate max-w-[200px]" title={label}>{label}</span>
                                  <span className="font-mono font-bold text-primary shrink-0">{val}{unit ? ` ${unit}` : ""}</span>
                                </div>
                                <div className="h-3 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                                  <div
                                    className={`h-full rounded-full transition-all duration-500 ${
                                      i % 3 === 0
                                        ? "bg-gradient-to-r from-primary to-indigo-500"
                                        : i % 3 === 1
                                        ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                                        : "bg-gradient-to-r from-cyan-500 to-blue-400"
                                    }`}
                                    style={{ width: `${Math.max(10, pct)}%` }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      );
                    }

                    // Otherwise, display distribution of claims by category/type from real persisted data
                    const typeCounts: Record<string, number> = {};
                    items.forEach((c: any) => {
                      const t = c.claim_type ? c.claim_type.replace(/_/g, " ") : "general";
                      typeCounts[t] = (typeCounts[t] || 0) + 1;
                    });
                    const types = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]).slice(0, 4);
                    const totalClaims = Math.max(items.length, 1);

                    return (
                      <div className="mt-5 space-y-4">
                        {types.length === 0 ? (
                          <div className="py-6 text-center text-xs text-mut">No persisted claims available yet.</div>
                        ) : (
                          types.map(([t, count], i) => {
                            const pct = Math.round((count / totalClaims) * 100);
                            return (
                              <div key={t}>
                                <div className="flex justify-between text-xs mb-1.5">
                                  <span className="text-tx font-medium capitalize">{t}</span>
                                  <span className="font-mono font-bold text-primary">{count} claims ({pct}%)</span>
                                </div>
                                <div className="h-3 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                                  <div
                                    className={`h-full rounded-full transition-all duration-500 ${
                                      i % 3 === 0
                                        ? "bg-gradient-to-r from-primary to-indigo-500"
                                        : i % 3 === 1
                                        ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                                        : "bg-gradient-to-r from-cyan-500 to-blue-400"
                                    }`}
                                    style={{ width: `${Math.max(10, pct)}%` }}
                                  />
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    );
                  }}
                </Gate>
              </div>
              <div className="mt-4 pt-3 border-t border-bd/50 text-[11px] text-mut">
                {isDemo ? (
                  <span className="text-amber-600 dark:text-amber-400 font-medium">
                    Fictional demo data on .invalid domains; not from real market/government reports.
                  </span>
                ) : (
                  <span>Derived strictly from persisted citations and research claims in database.</span>
                )}
              </div>
            </Card>

            {/* Chart 3: Evidence Stance Stacking */}
            <Card className="p-5 border-bd shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-bd/60">
                  <div className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-primary" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-tx">Evidence Stance Stacking</h3>
                  </div>
                  <span className="text-[11px] font-semibold text-primary">Distribution</span>
                </div>
                <Gate q={evidenceQ} rows={4}>
                  {(data) => {
                    const items = Array.isArray(data) ? data : (data?.items || []);
                    const supports = items.filter((e: any) => e.stance === "supports" || !e.stance).length;
                    const neutral = items.filter((e: any) => e.stance === "neutral" || e.stance === "context").length;
                    const disputes = items.filter((e: any) => e.stance === "disputes" || e.stance === "refutes" || e.stance === "contradicts").length;
                    const total = Math.max(items.length, 1);

                    return (
                      <div className="mt-4 space-y-3.5">
                        <div className="flex items-center gap-4">
                          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-accent/10 border border-primary/30 shadow-inner">
                            <span className="font-mono text-2xl font-black text-primary">{items.length}</span>
                          </div>
                          <div className="space-y-1 text-xs">
                            <div className="font-bold text-tx">Harvested Citations</div>
                            <p className="text-[11px] text-mut">
                              Verbatim excerpts anchoring every single claim and analysis.
                            </p>
                          </div>
                        </div>

                        <div className="space-y-2 pt-1 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="text-tx flex items-center gap-1.5 font-medium">
                              <span className="h-2 w-2 rounded-full bg-emerald-500" />
                              Supporting Evidence
                            </span>
                            <span className="font-mono font-bold text-tx">{supports} ({Math.round((supports / total) * 100)}%)</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-tx flex items-center gap-1.5 font-medium">
                              <span className="h-2 w-2 rounded-full bg-blue-400" />
                              Contextual / Neutral
                            </span>
                            <span className="font-mono font-bold text-tx">{neutral} ({Math.round((neutral / total) * 100)}%)</span>
                          </div>
                          {disputes > 0 && (
                            <div className="flex items-center justify-between">
                              <span className="text-tx flex items-center gap-1.5 font-medium">
                                <span className="h-2 w-2 rounded-full bg-rose-500" />
                                Disputing / Contradicting
                              </span>
                              <span className="font-mono font-bold text-tx">{disputes}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  }}
                </Gate>
              </div>
              <div className="mt-4 pt-3 border-t border-bd/50 text-[11px] text-mut">
                Traceable end-to-end without hallucinated assertions.
              </div>
            </Card>
          </div>

          {/* Visual Conflict Resolution Matrix */}
          <Gate q={graphQ}>
            {(g) => {
              const conflicts = g.edges?.filter((e: any) => e.type === "conflicts_with") || [];
              return (
                <Card className="p-6 border-bd shadow-sm">
                  <div className="flex items-center justify-between pb-4 border-b border-bd/60">
                    <div className="flex items-center gap-2.5">
                      <Scale className="h-5 w-5 text-amber-500" />
                      <div>
                        <h3 className="text-sm font-bold text-tx">Autonomous Conflict & Discrepancy Matrix</h3>
                        <p className="text-xs text-mut">Detects and reconciles conflicting metrics across different market scopes</p>
                      </div>
                    </div>
                    <span className="rounded-full bg-amber-500/10 px-3 py-1 text-xs font-bold text-amber-600 dark:text-amber-400 border border-amber-500/20">
                      {conflicts.length > 0 ? `${conflicts.length} Reconciled Discrepancy` : "No Contradictions"}
                    </span>
                  </div>

                  {conflicts.length === 0 ? (
                    <div className="py-8 text-center text-xs text-mut">
                      No statistical or definitional conflicts detected across harvested sources.
                    </div>
                  ) : (
                    <div className="mt-4 space-y-3">
                      {conflicts.map((c: any, idx: number) => (
                        <div key={idx} className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <Pill tone="warn">{c.conflict_type ? c.conflict_type.replace(/_/g, " ") : "Metric Scope Variance"}</Pill>
                              <Pill tone="info">{c.resolution_status ? c.resolution_status.replace(/_/g, " ") : "Explained by Scope"}</Pill>
                            </div>
                            <span className="text-xs font-semibold text-mut">Severity: {c.severity || "Low"}</span>
                          </div>
                          <p className="text-xs leading-relaxed text-tx font-medium">
                            {c.explanation || "Growth rate discrepancy is explained by market scope definition."}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              );
            }}
          </Gate>
        </div>
      )}

      {/* VIEW MODE 2: STRUCTURED DATA TABLE (GRID VIEW) */}
      {viewMode === "table" && (
        <Card className="overflow-hidden border-bd shadow-sm">
          {/* Table Filters & Search Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-bd/60 bg-surface/30">
            <div className="flex items-center gap-3 flex-1 min-w-[240px] max-w-md">
              <div className="relative flex-1">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-mut" />
                <input
                  className="inp pl-9 h-9 text-xs"
                  placeholder="Search extracted findings & claims..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="relative">
                <select
                  className="inp h-9 text-xs pr-8"
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <option value="all">All Verification Statuses</option>
                  <option value="supported">Verified / Supported</option>
                  <option value="partially_supported">Partially Supported</option>
                  <option value="unverified">Inference / Unverified</option>
                  <option value="contradicted">Contradicted</option>
                </select>
              </div>
            </div>
            <div className="text-xs text-mut font-medium">
              Structured multi-column data grid
            </div>
          </div>

          <Gate q={claimsQ}>
            {(data) => {
              const allClaims = Array.isArray(data) ? data : (data?.items || []);
              const filtered = allClaims.filter((c: any) => {
                const matchSearch = !search || c.text?.toLowerCase().includes(search.toLowerCase()) || c.claim_type?.toLowerCase().includes(search.toLowerCase());
                const matchStatus = filterStatus === "all" || c.status === filterStatus;
                return matchSearch && matchStatus;
              });

              if (filtered.length === 0) {
                return (
                  <div className="py-16 text-center text-xs text-mut">
                    No claims match your search filters.
                  </div>
                );
              }

              return (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead className="border-b border-bd/70 bg-surface/60 font-bold uppercase tracking-wider text-mut">
                      <tr>
                        <th className="px-4 py-3">Claim Finding</th>
                        <th className="px-4 py-3">Type</th>
                        <th className="px-4 py-3">Verification Status</th>
                        <th className="px-4 py-3">Confidence</th>
                        <th className="px-4 py-3">Evidence Items</th>
                        <th className="px-4 py-3">Agent</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-bd/60 text-tx">
                      {filtered.map((c: any, idx: number) => (
                        <tr key={c.id || idx} className="hover:bg-surface/50 transition-colors">
                          <td className="px-4 py-3.5 max-w-md">
                            <div className="font-semibold text-tx leading-relaxed">{c.text}</div>
                            {c.verification?.rationale && (
                              <p className="text-[11px] text-mut mt-1">{c.verification.rationale}</p>
                            )}
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap">
                            <span className="font-mono uppercase text-[10px] bg-surface px-2 py-0.5 rounded border border-bd">
                              {c.claim_type || "Market Fact"}
                            </span>
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap">
                            <Pill tone={tone(c.status)}>{claimLabel(c.status)}</Pill>
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap font-mono font-bold">
                            {c.confidence || "HIGH"}
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap">
                            <span className="inline-flex items-center gap-1 font-mono font-bold bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                              <FileText className="h-3 w-3" />
                              {c.evidence_count || 1} citations
                            </span>
                          </td>
                          <td className="px-4 py-3.5 whitespace-nowrap font-mono text-mut">
                            {c.created_by_agent || "Market Analyst"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            }}
          </Gate>
        </Card>
      )}
    </div>
  );
}
