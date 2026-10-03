"use client";
import ResearchScoped from "@/components/ResearchScoped";
import Shell from "@/components/Shell";
import { ClaimsView } from "@/components/views/DataViews";
export default function Page() { return <Shell title="Claims" sub="Select a research project"><ResearchScoped render={(rid) => <ClaimsView rid={rid} />} /></Shell>; }
