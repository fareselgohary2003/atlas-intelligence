"use client";
import ResearchScoped from "@/components/ResearchScoped";
import Shell from "@/components/Shell";
import ReportView from "@/components/views/ReportView";
export default function Page() { return <Shell title="Reports" sub="Select a research project"><ResearchScoped render={(rid) => <ReportView rid={rid} />} /></Shell>; }
