"use client";
import ResearchScoped from "@/components/ResearchScoped";
import Shell from "@/components/Shell";
import { EvidenceView } from "@/components/views/DataViews";
export default function Page() { return <Shell title="Evidence" sub="Select a research project"><ResearchScoped render={(rid) => <EvidenceView rid={rid} />} /></Shell>; }
