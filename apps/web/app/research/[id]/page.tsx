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
          ["Competitors", r.competitors?.join(", ") || "—"],
          ["Owner", r.owner],
          ["Created", r.created_at?.slice(0, 10)],
        ];
        return (
          <div className="space-y-4 max-w-4xl animate-fade-in">
            <Card className="p-5 border-bd shadow-sm">
              <h3 className="text-xs font-bold uppercase tracking-wider text-mut mb-2">Research Objective</h3>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-tx font-medium">{r.objective}</p>
            </Card>
            <Card className="p-5 border-bd shadow-sm">
              <h3 className="text-xs font-bold uppercase tracking-wider text-mut mb-3">Project Metadata</h3>
              <dl className="grid md:grid-cols-2 gap-y-3 gap-x-6 text-xs">
                {rows.map(([k, v]) => (
                  <div key={k} className="flex justify-between border-b border-bd/50 pb-2">
                    <dt className="text-mut font-medium">{k}</dt>
                    <dd className="font-semibold text-tx">{v || "—"}</dd>
                  </div>
                ))}
              </dl>
            </Card>
            {canWrite(ws) && (
              <button
                className="btn text-danger hover:bg-danger/10 border-danger/30 text-xs"
                onClick={async () => {
                  if (confirm("Delete this research project and all its data?")) {
                    await api("/api/research/" + rid, { method: "DELETE" });
                    router.push("/research");
                  }
                }}
              >
                Delete Research Project
              </button>
            )}
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
      {/* Project Header Title */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-bd/60 pb-3">
        <div className="flex items-center gap-2.5">
          <h1 className="text-xl font-bold tracking-tight text-tx">{p.data?.title}</h1>
          {p.data?.is_demo && <Mock />}
        </div>
        <div className="flex items-center gap-2">
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
