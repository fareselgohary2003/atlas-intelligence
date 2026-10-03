"use client";
import ResearchScoped from "@/components/ResearchScoped";
import Shell from "@/components/Shell";
import { SourcesView } from "@/components/views/DataViews";
export default function Page() { return <Shell title="Sources" sub="Select a research project"><ResearchScoped render={(rid) => <SourcesView rid={rid} />} /></Shell>; }
