"use client";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";
import Shell, { canWrite, useSession } from "@/components/Shell";
import LiveWorkspace from "@/components/views/LiveWorkspace";
import { ClaimsView, EvidenceView, SourcesView } from "@/components/views/DataViews";
import GraphView from "@/components/views/GraphView";
import ReportView from "@/components/views/ReportView";
import VisualAnalyticsView from "@/components/views/VisualAnalyticsView";
import { Card, Gate, Mock } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import {
  LayoutDashboard,
  BarChart3,
  Network,
  Gavel,
  FileText,
  Database,
  FileSignature,
  FileSpreadsheet,
  Sparkles,
} from "lucide-react";

const TABS = [
  { key: "workspace", label: "Workspace", icon: LayoutDashboard },
  { key: "visuals", label: "Visual Insights", icon: BarChart3, badge: "Charts" },
  { key: "graph", label: "Knowledge Graph", icon: Network, badge: "Interactive" },
  { key: "claims", label: "Claims", icon: Gavel },
  { key: "evidence", label: "Evidence", icon: FileText },
  { key: "sources", label: "Sources", icon: Database },
  { key: "report", label: "Executive Report", icon: FileSignature },
  { key: "brief", label: "Brief Info", icon: FileSpreadsheet },
];

function Brief({ rid }: { rid: string }) {
  const { ws } = useSession(), router = useRouter();
  const q = useApi<any>(`/api/research/${rid}`);
  return (
    <Gate q={q}>
      {(r) => {
        const rows = [
          ["Industry", r.industry],
          ["Geography", r.geography],
          ["Target customer", r.target_customer],
          ["Time range", r.time_range],
          ["Depth", r.depth],
          ["Owner", r.owner],
          ["Created", r.created_at?.slice(0, 10)],
        ];
        return (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 animate-fade-in">
            {/* Left 2 Cols: Research Objective & Scope */}
            <div className="lg:col-span-2 space-y-4">
              <Card className="p-6 border-bd shadow-sm">
                <div className="flex items-center justify-between pb-3 mb-3 border-b border-bd/60">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-primary">Strategic Research Objective</h3>
                  <span className="text-[11px] text-mut font-medium">Core Scope Definition</span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-tx font-medium">{r.objective}</p>
              </Card>

              <Card className="p-6 border-bd shadow-sm">
                <div className="flex items-center justify-between pb-3 mb-3 border-b border-bd/60">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-tx">Target Customer & Market Parameters</h3>
                  <span className="text-[11px] text-mut font-medium">{r.industry || "General Industry"}</span>
                </div>
                <div className="grid sm:grid-cols-2 gap-4 text-xs">
                  <div className="rounded-xl border border-bd/70 bg-surface/50 p-3.5">
                    <div className="text-[11px] font-semibold text-mut uppercase tracking-wide">Target Segment</div>
                    <div className="mt-1 font-semibold text-sm text-tx">{r.target_customer || "Unspecified"}</div>
                  </div>
                  <div className="rounded-xl border border-bd/70 bg-surface/50 p-3.5">
                    <div className="text-[11px] font-semibold text-mut uppercase tracking-wide">Geographic Focus</div>
                    <div className="mt-1 font-semibold text-sm text-tx">{r.geography || "Global / Unrestricted"}</div>
                  </div>
                  <div className="rounded-xl border border-bd/70 bg-surface/50 p-3.5">
                    <div className="text-[11px] font-semibold text-mut uppercase tracking-wide">Evaluation Period</div>
                    <div className="mt-1 font-semibold text-sm text-tx">{r.time_range || "Current Baseline"}</div>
                  </div>
                  <div className="rounded-xl border border-bd/70 bg-surface/50 p-3.5">
                    <div className="text-[11px] font-semibold text-mut uppercase tracking-wide">Analysis Depth</div>
                    <div className="mt-1 font-semibold text-sm text-tx capitalize">{r.depth || "Deep Research"}</div>
                  </div>
                </div>
              </Card>
            </div>

            {/* Right 1 Col: Metadata, Competitors & Administrative Controls */}
            <div className="space-y-4">
              <Card className="p-5 border-bd shadow-sm">
                <h3 className="text-xs font-bold uppercase tracking-wider text-tx mb-3 pb-2 border-b border-bd/60">Project Attributes</h3>
                <dl className="space-y-2.5 text-xs">
                  {rows.map(([k, v]) => (
                    <div key={k} className="flex justify-between items-center py-1 border-b border-bd/40 last:border-0">
                      <dt className="text-mut font-medium">{k}</dt>
                      <dd className="font-semibold text-tx">{v || "—"}</dd>
                    </div>
                  ))}
                </dl>
              </Card>

              {r.competitors && r.competitors.length > 0 && (
                <Card className="p-5 border-bd shadow-sm">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-tx mb-2">Tracked Competitors</h3>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {r.competitors.map((c: string) => (
                      <span key={c} className="rounded-lg bg-surface border border-bd px-2.5 py-1 text-xs font-medium text-tx">
                        {c}
                      </span>
                    ))}
                  </div>
                </Card>
              )}

              {canWrite(ws) && (
                <Card className="p-4 border-danger/30 bg-danger/5 shadow-sm">
                  <h4 className="text-xs font-bold text-danger mb-1">Administrative Actions</h4>
                  <p className="text-[11px] text-mut mb-3">Irreversible deletion of all gathered evidence and claims for this project.</p>
                  <button
                    className="btn w-full text-danger hover:bg-danger/10 border-danger/30 text-xs font-semibold"
                    onClick={async () => {
                      if (confirm("Delete this research project and all its data?")) {
                        await api("/api/research/" + rid, { method: "DELETE" });
                        router.push("/research");
                      }
                    }}
                  >
                    Delete Research Project
                  </button>
                </Card>
              )}
            </div>
          </div>
        );
      }}
    </Gate>
  );
}

function Body() {
  const { id } = useParams<{ id: string }>();
  const tab = useSearchParams().get("tab") || "workspace";
  const p = useApi<any>(`/api/research/${id}`);

  return (
    <div className="space-y-4">
      {/* Project Header Title with Full Wrapping & No Truncation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-bd/60 pb-3">
        <div className="flex items-start gap-2.5 flex-1 min-w-0">
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl md:text-2xl font-bold tracking-tight text-tx break-words whitespace-normal leading-snug">
                {p.data?.title || "Research Project"}
              </h1>
              {p.data?.is_demo && <Mock />}
            </div>
            {p.data?.objective && (
              <p className="mt-1 text-xs text-mut line-clamp-1 break-words">
                {p.data.objective}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Link
            href={`/research/${id}?tab=visuals`}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
              tab === "visuals"
                ? "bg-primary text-white shadow-sm"
                : "bg-primary/10 text-primary hover:bg-primary/20"
            }`}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            <span>Open Charts & Visuals</span>
          </Link>
          <Link
            href={`/research/${id}?tab=graph`}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
              tab === "graph"
                ? "bg-accent text-white shadow-sm"
                : "bg-accent/10 text-accent hover:bg-accent/20"
            }`}
          >
            <Network className="h-3.5 w-3.5" />
            <span>Interactive Graph</span>
          </Link>
        </div>
      </div>

      {/* Tabs Navigation */}
      <nav className="flex flex-wrap gap-1.5 border-b border-bd/70 pb-px" aria-label="Research sections">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <Link
              key={t.key}
              href={`/research/${id}?tab=${t.key}`}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-t-lg transition-all ${
                active
                  ? "border-b-2 border-primary bg-primary/5 text-primary font-bold shadow-sm"
                  : "text-mut hover:bg-surface hover:text-tx"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{t.label}</span>
              {t.badge && (
                <span className="ml-1 rounded-full bg-primary/15 px-1.5 py-0.2 text-[9px] font-bold text-primary">
                  {t.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Tab Content */}
      <div className="pt-2">
        {tab === "workspace" && <LiveWorkspace rid={id} />}
        {tab === "visuals" && <VisualAnalyticsView rid={id} />}
        {tab === "graph" && <GraphView rid={id} />}
        {tab === "claims" && <ClaimsView rid={id} />}
        {tab === "evidence" && <EvidenceView rid={id} />}
        {tab === "sources" && <SourcesView rid={id} />}
        {tab === "report" && <ReportView rid={id} />}
        {tab === "brief" && <Brief rid={id} />}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Shell title="Research Project">
      <Suspense fallback={<div className="h-10 w-64 animate-pulse rounded-lg bg-bd/50" />}>
        <Body />
      </Suspense>
    </Shell>
  );
}
