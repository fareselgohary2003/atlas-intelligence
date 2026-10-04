"use client";
import { useState, useMemo } from "react";
import { Pill } from "../ui";
import { Search, Filter, ExternalLink, Quote, Sparkles, FileDown } from "lucide-react";
import SourceModal, { SourceInfo } from "../SourceModal";

const TONE: Record<string, string> = {
  VERIFIED: "ok",
  "PARTIALLY SUPPORTED": "warn",
  UNVERIFIED: "muted",
  CONTRADICTED: "bad",
  INFERENCE: "info",
  UNCERTAINTY: "muted",
};

export default function ExecutiveReportTable({
  report,
  rid,
  compact = false,
}: {
  report: any;
  rid: string;
  compact?: boolean;
}) {
  const [search, setSearch] = useState("");
  const [filterSection, setFilterSection] = useState("all");
  const [selectedSource, setSelectedSource] = useState<SourceInfo | null>(null);

  // Extract all findings from report sections
  const allFindings = useMemo(() => {
    if (!report?.sections) return [];
    const rows: any[] = [];
    const citationsMap = new Map((report.citations || []).map((c: any) => [c.n, c]));

    report.sections.forEach((s: any) => {
      if (s.key === "sources" || s.key === "claims_appendix") return;

      // Regular findings
      (s.findings || []).forEach((f: any) => {
        const cites = (f.citations || []).map((n: number) => citationsMap.get(n)).filter(Boolean);
        rows.push({
          id: f.claim_id || Math.random().toString(),
          sectionKey: s.key,
          sectionTitle: s.title,
          text: f.text,
          label: f.label || "VERIFIED",
          confidence: f.confidence || "MEDIUM",
          rationale: f.rationale,
          citations: f.citations || [],
          citationSources: cites,
          evidence: f.evidence || [],
          attributes: f.attributes || {},
          kind: "finding",
        });
      });

      // Analytical inferences
      (s.analysis || []).forEach((a: any) => {
        const cites = (a.citations || []).map((n: number) => citationsMap.get(n)).filter(Boolean);
        rows.push({
          id: a.analysis_id || Math.random().toString(),
          sectionKey: s.key,
          sectionTitle: s.title,
          text: a.text,
          label: a.label || "INFERENCE",
          confidence: "HIGH",
          rationale: a.basis?.map((b: any) => b.text).join(" • "),
          citations: a.citations || [],
          citationSources: cites,
          evidence: [],
          attributes: {},
          kind: "analysis",
        });
      });
    });

    return rows;
  }, [report]);

  // Filtered rows
  const filtered = useMemo(() => {
    return allFindings.filter((item) => {
      if (filterSection !== "all" && item.sectionKey !== filterSection) {
        return false;
      }
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        item.text.toLowerCase().includes(q) ||
        item.sectionTitle.toLowerCase().includes(q) ||
        (item.attributes?.metric && item.attributes.metric.toLowerCase().includes(q)) ||
        (item.attributes?.value && String(item.attributes.value).toLowerCase().includes(q)) ||
        (item.rationale && item.rationale.toLowerCase().includes(q))
      );
    });
  }, [allFindings, filterSection, search]);

  const sections = useMemo(() => {
    const set = new Set(allFindings.map((f) => f.sectionKey));
    return Array.from(set).map((key) => {
      const found = allFindings.find((f) => f.sectionKey === key);
      return { key, title: found?.sectionTitle || key };
    });
  }, [allFindings]);

  return (
    <div className="space-y-4">
      {/* Search & Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-surface/40 p-3 rounded-xl border border-bd">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-mut" />
          <input
            type="text"
            placeholder="Search report findings, metrics, competitors..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="inp pl-9 w-full text-xs h-9"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-mut" />
          <select
            value={filterSection}
            onChange={(e) => setFilterSection(e.target.value)}
            className="inp text-xs h-9 min-w-[180px]"
            aria-label="Filter by report section"
          >
            <option value="all">All Sections ({allFindings.length})</option>
            {sections.map((s) => (
              <option key={s.key} value={s.key}>
                {s.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Structured Table */}
      <div className="overflow-x-auto rounded-xl border border-bd bg-card shadow-sm">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-bd bg-surface/70 text-[11px] font-bold uppercase tracking-wider text-mut">
              <th className="px-4 py-3">Section</th>
              <th className="px-4 py-3 min-w-[280px]">Finding / Proposition</th>
              <th className="px-4 py-3">Metric & Figure</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Evidence & Citations</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-bd text-xs">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-mut italic">
                  No findings matched your criteria.
                </td>
              </tr>
            ) : (
              filtered.map((row) => (
                <tr
                  key={row.id}
                  className="transition-colors hover:bg-surface/50 group"
                >
                  <td className="px-4 py-3 align-top font-semibold text-tx/80 whitespace-nowrap">
                    <span className="rounded-md bg-surface px-2 py-1 border border-bd/60 text-[10px]">
                      {row.sectionTitle}
                    </span>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <p className="text-sm font-medium text-tx leading-relaxed">
                      {row.text}
                    </p>
                    {row.rationale && (
                      <p className="mt-1 text-[11px] text-mut leading-normal">
                        {row.rationale}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top whitespace-nowrap">
                    {row.attributes?.value != null ? (
                      <div className="rounded-lg bg-primary/5 border border-primary/20 p-2 font-mono">
                        <div className="text-[10px] text-mut uppercase">
                          {row.attributes.metric || "Extracted Value"}
                        </div>
                        <div className="text-sm font-bold text-tx">
                          {row.attributes.value} {row.attributes.unit || ""}
                        </div>
                        {row.attributes.period && (
                          <div className="text-[10px] text-mut">
                            Period: {row.attributes.period}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-mut text-[11px]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top whitespace-nowrap">
                    <Pill tone={TONE[row.label]}>{row.label}</Pill>
                  </td>
                  <td className="px-4 py-3 align-top whitespace-nowrap">
                    <span className="font-semibold text-tx">{row.confidence}</span>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {row.citations.map((n: number) => {
                        const src = row.citationSources.find((c: any) => c.n === n);
                        return (
                          <button
                            key={n}
                            onClick={() =>
                              setSelectedSource(
                                src || {
                                  n,
                                  title: `Source [${n}]`,
                                  url: "",
                                }
                              )
                            }
                            className="inline-flex items-center gap-1 rounded bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary hover:bg-primary/20 hover:scale-105 transition-all"
                            title={src?.title || `Inspect Source [${n}]`}
                          >
                            <span>[{n}]</span>
                            <Quote className="h-2.5 w-2.5" />
                          </button>
                        );
                      })}
                    </div>
                    {row.evidence?.length > 0 && (
                      <div className="mt-1.5 text-[10px] text-mut italic line-clamp-2 max-w-xs">
                        “{row.evidence[0]?.excerpt}”
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Source Reader Modal */}
      {selectedSource && (
        <SourceModal
          rid={rid}
          source={selectedSource}
          onClose={() => setSelectedSource(null)}
        />
      )}
    </div>
  );
}
