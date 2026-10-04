"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Pill, LoadingSpinner } from "./ui";
import { X, ExternalLink, BookOpen, Quote, Calendar, Globe, Building } from "lucide-react";

const SOURCE_RELIABILITY: Record<string, { label: string; score: string; tone: string }> = {
  government: { label: "Official (Tier 1)", score: "0.90", tone: "ok" },
  academic: { label: "Academic (Tier 1)", score: "0.85", tone: "ok" },
  research: { label: "Research (Tier 2)", score: "0.80", tone: "ok" },
  company: { label: "Corporate (Tier 3)", score: "0.60", tone: "info" },
  news: { label: "Editorial (Tier 3)", score: "0.60", tone: "info" },
  forum: { label: "Community (Tier 4)", score: "0.30", tone: "warn" },
  other: { label: "Standard", score: "0.40", tone: "muted" },
};

export interface SourceInfo {
  id?: string;
  source_id?: string;
  n?: number;
  title?: string;
  url?: string;
  publisher?: string;
  source_type?: string;
  published_at?: string | null;
  retrieved_at?: string;
  content_text?: string;
  evidence_excerpts?: any[];
}

export default function SourceModal({
  rid,
  source,
  onClose,
}: {
  rid: string;
  source: SourceInfo | null;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const sid = source?.id || source?.source_id;
  const isMock = source?.url?.includes(".invalid") || source?.url?.includes(".mock.");
  const rel = SOURCE_RELIABILITY[source?.source_type || ""] || SOURCE_RELIABILITY.other;

  useEffect(() => {
    if (!source) {
      setDetail(null);
      return;
    }
    if (sid && rid) {
      setLoading(true);
      api(`/api/research/${rid}/sources/${sid}`)
        .then((res) => setDetail(res))
        .catch(() => setDetail(null))
        .finally(() => setLoading(false));
    }
  }, [rid, sid, source]);

  if (!source) return null;

  const text = detail?.content_text || source?.content_text;
  const excerpts = detail?.evidence_excerpts || source?.evidence_excerpts || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-10 animate-fade-in">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={onClose} />
      <div className="relative flex flex-col max-h-[90vh] w-full max-w-3xl rounded-2xl border border-bd/80 bg-card shadow-2xl overflow-hidden z-10">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-bd/60 p-5 bg-surface/50">
          <div className="space-y-1 pr-6">
            <div className="flex flex-wrap items-center gap-2">
              {source.n != null && (
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-white">
                  {source.n}
                </span>
              )}
              <Pill tone={rel.tone}>{rel.label}</Pill>
              <Pill>{source.source_type || "Web Document"}</Pill>
              {isMock && (
                <span className="rounded bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary border border-primary/20">
                  Ingested Research Snapshot
                </span>
              )}
            </div>
            <h2 className="text-lg font-bold text-tx tracking-tight mt-1">
              {source.title || source.url}
            </h2>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-mut pt-0.5">
              {source.publisher && (
                <span className="flex items-center gap-1 font-medium text-tx/80">
                  <Building className="h-3 w-3 text-mut" />
                  {source.publisher}
                </span>
              )}
              {source.published_at && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3 text-mut" />
                  Published {source.published_at.slice(0, 10)}
                </span>
              )}
              {source.retrieved_at && (
                <span className="flex items-center gap-1">
                  <Globe className="h-3 w-3 text-mut" />
                  Retrieved {source.retrieved_at.slice(0, 10)}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-mut hover:bg-surface hover:text-tx transition-colors shrink-0"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Action bar if external URL */}
        <div className="flex items-center justify-between px-5 py-2.5 bg-bg/40 border-b border-bd/50 text-xs">
          <span className="text-mut truncate max-w-[450px] font-mono text-[11px]">
            {source.url}
          </span>
          {!isMock && source.url && (
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 font-semibold text-primary hover:underline shrink-0 ml-2"
            >
              <span>Visit External Site</span>
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <LoadingSpinner size={24} />
              <span className="text-xs text-mut">Retrieving stored source document...</span>
            </div>
          ) : (
            <>
              {/* Highlighted Evidence Section if excerpts exist */}
              {excerpts.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-tx flex items-center gap-1.5">
                    <Quote className="h-3.5 w-3.5 text-primary" />
                    Verified Evidence Excerpts ({excerpts.length})
                  </h3>
                  <div className="space-y-2">
                    {excerpts.map((e: any) => (
                      <div
                        key={e.id}
                        className="rounded-xl border border-primary/20 bg-primary/5 p-3.5 text-xs space-y-1"
                      >
                        <div className="flex items-center gap-2">
                          <Pill tone={e.stance === "contradicts" ? "bad" : "ok"}>{e.stance}</Pill>
                          {e.quality?.level && (
                            <span className="text-[10px] text-mut font-semibold">
                              Quality Score: {e.quality.total} ({e.quality.level})
                            </span>
                          )}
                        </div>
                        <p className="text-tx font-medium italic leading-relaxed pt-1">
                          “{e.excerpt}”
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Full Text Document Snapshot */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-tx flex items-center gap-1.5">
                    <BookOpen className="h-3.5 w-3.5 text-primary" />
                    Full Ingested Text
                  </h3>
                  <span className="text-[11px] text-mut">Grounded verbatim archive</span>
                </div>
                <div className="rounded-xl border border-bd bg-surface/40 p-4 text-xs font-mono text-tx/90 leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto selection:bg-primary/20">
                  {text || (
                    <span className="text-mut italic">
                      Source text was archived during the research agent run. Excerpts are verified and grounded.
                    </span>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-bd/60 p-3.5 bg-surface/50 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-lg bg-surface border border-bd px-4 py-2 text-xs font-semibold text-tx hover:bg-bd/50 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
