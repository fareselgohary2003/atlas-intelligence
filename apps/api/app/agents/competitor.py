from app.agents.framework import AgentDefinition
from app.agents.pipeline import ResearchPipelineAgent

TOOLS = ("web_search", "fetch_url", "extract_page_content", "save_source", "create_claim", "create_evidence", "request_research", "update_task")


class CompetitorResearchAgent(ResearchPipelineAgent):
    definition = AgentDefinition("competitor", "Competitor Research Agent",
                                 "Identifies competitors and records product, customers, pricing and positioning with evidence.",
                                 ("competitor_identity", "pricing", "positioning"), TOOLS)
    dimensions = (("competitor identity", "competitor_profile", ("competitor", "company", "landscape", "vendor")),
                  ("pricing", "pricing", ("pricing", "price")),
                  ("positioning", "positioning", ("positioning", "target")))
    claim_types = ("competitor_profile", "pricing", "positioning")
    query_suffixes = ("competitors pricing", "product features target customers")
    extract_system = (
        "You extract competitor evidence for a research task from ONE source. Return ONLY JSON: "
        '{"findings":[{"excerpt":"<text copied EXACTLY from the source>","claim":"<one factual statement the excerpt supports>",'
        '"claim_type":"<competitor_profile|pricing|positioning>","stance":"supports|contradicts",'
        '"attributes":{"company":"","product":"","target_customers":"","geography":"","price":"","currency":"","pricing_status":"available|unavailable"}}]}. '
        "Rules: copy excerpts verbatim; never infer or invent prices; if the source says pricing is not published use "
        'pricing_status "unavailable" and no price; omit attributes the source does not state; if nothing relevant return {"findings":[]}.')

    def finalize(self, task, claims, md):
        comps = {}
        for c in claims:
            name = str(c["attributes"].get("company") or "").strip()
            if not name:
                continue
            d = comps.setdefault(name, {"claim_ids": [], "source_ids": [], "pricing_status": "unavailable"})
            d["claim_ids"].append(c["claim_id"])
            if c["source_id"] not in d["source_ids"]:
                d["source_ids"].append(c["source_id"])
            a = c["attributes"]
            if c["claim_type"] == "pricing" and a.get("price") and a.get("pricing_status") != "unavailable":
                d["pricing_status"] = "available"  # only a grounded pricing claim that states a price makes it available
        md["competitors"] = comps
