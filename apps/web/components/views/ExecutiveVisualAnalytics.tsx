"use client";
import { useMemo } from "react";
import { Card } from "../ui";
import { CheckCircle2, AlertTriangle, HelpCircle, XCircle, TrendingUp, Layers, BookOpen, BarChart3 } from "lucide-react";

export default function ExecutiveVisualAnalytics({
  report,
  summary,
}: {
  report?: any;
  summary?: any;
}) {
  const stats = report?.stats || {};
  const byGroup = stats.by_group || {};
  const verified = byGroup.verified || 0;
  const partial = byGroup.partial || 0;
  const uncertain = byGroup.uncertain || 0;
  const contradicted = byGroup.contradicted || 0;
  const totalClaims = (stats.claims || verified + partial + uncertain + contradicted) || 1;

  // Extract quantitative metrics with values from report findings
  const metricFindings = useMemo(() => {
    if (!report?.sections) return [];
    const list: any[] = [];
    report.sections.forEach((s: any) => {
      (s.findings || []).forEach((f: any) => {
        if (f.attributes?.value != null) {
          list.push({
            title: f.attributes.metric || f.text.slice(0, 35) + "...",
            val: Number(f.attributes.value),
            unit: f.attributes.unit || "",
            period: f.attributes.period || "",
            status: f.label,
          });
        }
      });
    });
    return list;
  }, [report]);

  // Source Authority Breakdown
  const sourceStats = useMemo(() => {
    const citations = report?.citations || [];
    const counts: Record<string, number> = {
      government: 0,
      academic: 0,
      research: 0,
      company: 0,
      news: 0,
      other: 0,
    };
    citations.forEach((c: any) => {
      const t = (c.source_type || "other").toLowerCase();
      if (counts[t] !== undefined) counts[t]++;
      else counts.other++;
    });
    return counts;
  }, [report]);

  const maxMetricVal = useMemo(() => {
    if (metricFindings.length === 0) return 100;
    return Math.max(...metricFindings.map((m) => m.val), 1);
  }, [metricFindings]);

  return (
    <div className="space-y-6">
      {/* Top Visual Cards: 3 Dimensional Overview */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Verification Rate Gauge */}
        <Card className="p-4 border-emerald-500/20 bg-gradient-to-br from-card to-emerald-500/5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold text-emerald-600 dark:text-emerald-400">
            <span>Verified Grounding</span>
            <CheckCircle2 className="h-4 w-4" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-tx tracking-tight">
              {Math.round((verified / totalClaims) * 100)}%
            </span>
            <span className="text-xs text-mut font-medium">({verified} / {totalClaims} claims)</span>
          </div>
          <div className="mt-3 h-2 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-500"
              style={{ width: `${Math.round((verified / totalClaims) * 100)}%` }}
            />
          </div>
          <div className="mt-2 text-[11px] text-mut">Corroborated by independent primary sources</div>
        </Card>

        {/* Partial Support */}
        <Card className="p-4 border-amber-500/20 bg-gradient-to-br from-card to-amber-500/5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold text-amber-600 dark:text-amber-400">
            <span>Partially Supported</span>
            <AlertTriangle className="h-4 w-4" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-tx tracking-tight">
              {Math.round((partial / totalClaims) * 100)}%
            </span>
            <span className="text-xs text-mut font-medium">({partial} claims)</span>
          </div>
          <div className="mt-3 h-2 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
            <div
              className="h-full rounded-full bg-amber-500 transition-all duration-500"
              style={{ width: `${Math.round((partial / totalClaims) * 100)}%` }}
            />
          </div>
          <div className="mt-2 text-[11px] text-mut">Single-source or scoped context</div>
        </Card>

        {/* Inferences & Insights */}
        <Card className="p-4 border-indigo-500/20 bg-gradient-to-br from-card to-indigo-500/5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold text-indigo-600 dark:text-indigo-400">
            <span>Strategic Inferences</span>
            <TrendingUp className="h-4 w-4" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-tx tracking-tight">
              {stats.analysis || 0}
            </span>
            <span className="text-xs text-mut font-medium">inferences synthesized</span>
          </div>
          <div className="mt-3 h-2 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all duration-500"
              style={{ width: `${Math.min(100, ((stats.analysis || 1) / 10) * 100)}%` }}
            />
          </div>
          <div className="mt-2 text-[11px] text-mut">Derived opportunities & risk forecasts</div>
        </Card>

        {/* Source Citations */}
        <Card className="p-4 border-blue-500/20 bg-gradient-to-br from-card to-blue-500/5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold text-blue-600 dark:text-blue-400">
            <span>Sources Cited</span>
            <BookOpen className="h-4 w-4" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-tx tracking-tight">
              {report?.citations?.length || stats.sources || 0}
            </span>
            <span className="text-xs text-mut font-medium">referenced in report</span>
          </div>
          <div className="mt-3 h-2 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-500"
              style={{ width: "100%" }}
            />
          </div>
          <div className="mt-2 text-[11px] text-mut">SSRF-protected verified citations</div>
        </Card>
      </div>

      {/* Main Charts Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Chart 1: Verification Health Breakdown */}
        <Card className="p-5 border-bd shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-bd/60">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-tx">
                Claim Verification Distribution
              </h3>
            </div>
            <span className="text-[11px] text-mut font-mono">{totalClaims} total claims</span>
          </div>

          <div className="mt-5 space-y-4">
            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Verified & Supported
                </span>
                <span className="font-mono text-tx font-bold">{verified} ({Math.round((verified / totalClaims) * 100)}%)</span>
              </div>
              <div className="h-3 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                <div
                  className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                  style={{ width: `${(verified / totalClaims) * 100}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5" /> Partially Supported
                </span>
                <span className="font-mono text-tx font-bold">{partial} ({Math.round((partial / totalClaims) * 100)}%)</span>
              </div>
              <div className="h-3 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                <div
                  className="h-full rounded-full bg-amber-500 transition-all duration-500"
                  style={{ width: `${(partial / totalClaims) * 100}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="flex items-center gap-1.5 text-red-600 dark:text-red-400">
                  <XCircle className="h-3.5 w-3.5" /> Contradicted / Scope Conflict
                </span>
                <span className="font-mono text-tx font-bold">{contradicted} ({Math.round((contradicted / totalClaims) * 100)}%)</span>
              </div>
              <div className="h-3 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                <div
                  className="h-full rounded-full bg-red-500 transition-all duration-500"
                  style={{ width: `${(contradicted / totalClaims) * 100}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1.5 font-medium">
                <span className="flex items-center gap-1.5 text-muted-foreground text-mut">
                  <HelpCircle className="h-3.5 w-3.5" /> Unverified / Research Gaps
                </span>
                <span className="font-mono text-tx font-bold">{uncertain} ({Math.round((uncertain / totalClaims) * 100)}%)</span>
              </div>
              <div className="h-3 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                <div
                  className="h-full rounded-full bg-zinc-500 transition-all duration-500"
                  style={{ width: `${(uncertain / totalClaims) * 100}%` }}
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Chart 2: Source Authority Tiers */}
        <Card className="p-5 border-bd shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-bd/60">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-primary" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-tx">
                Source Authority & Reliability Tiers
              </h3>
            </div>
            <span className="text-[11px] text-mut font-mono">Weighted Credibility</span>
          </div>

          <div className="mt-5 space-y-3.5">
            {[
              { key: "government", label: "Government & Regulatory (0.90)", count: sourceStats.government, color: "bg-emerald-500" },
              { key: "academic", label: "Academic & Peer-Reviewed (0.85)", count: sourceStats.academic, color: "bg-teal-500" },
              { key: "research", label: "Independent Research Institutes (0.80)", count: sourceStats.research, color: "bg-blue-500" },
              { key: "company", label: "Corporate Filings & Vendor Profiles (0.60)", count: sourceStats.company, color: "bg-indigo-500" },
              { key: "news", label: "Industry Journalism & News (0.60)", count: sourceStats.news, color: "bg-violet-500" },
              { key: "other", label: "Unclassified Web Sources (0.40)", count: sourceStats.other, color: "bg-slate-500" },
            ].map((tier) => {
              const totalSources = report?.citations?.length || 1;
              const pct = Math.round((tier.count / totalSources) * 100);
              return (
                <div key={tier.key}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-tx/90 font-medium">{tier.label}</span>
                    <span className="font-mono text-mut font-bold">{tier.count} source{tier.count === 1 ? "" : "s"}</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                    <div
                      className={`h-full rounded-full ${tier.color} transition-all duration-500`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Chart 3: Quantitative Findings & Metrics Comparison */}
      {metricFindings.length > 0 && (
        <Card className="p-5 border-bd shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-bd/60">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-tx">
                Quantitative Market Figures & Extracted Metrics
              </h3>
            </div>
            <span className="text-[11px] text-mut">Values verified in source documents</span>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {metricFindings.map((item, idx) => (
              <div
                key={idx}
                className="rounded-xl border border-bd bg-surface/40 p-3.5 flex flex-col justify-between space-y-2 hover:border-primary/50 transition-all"
              >
                <div>
                  <div className="text-xs font-semibold text-tx leading-tight">
                    {item.title}
                  </div>
                  {item.period && (
                    <div className="text-[10px] text-mut mt-0.5">Period: {item.period}</div>
                  )}
                </div>
                <div>
                  <div className="text-xl font-bold font-mono text-primary tracking-tight">
                    {item.val} <span className="text-xs font-normal text-mut">{item.unit}</span>
                  </div>
                  <div className="mt-2 h-1.5 w-full rounded-full bg-surface overflow-hidden border border-bd/40">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-all duration-500"
                      style={{ width: `${Math.min(100, (item.val / maxMetricVal) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
