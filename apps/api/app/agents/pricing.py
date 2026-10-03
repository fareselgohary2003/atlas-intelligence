from app.agents.framework import AgentDefinition
from app.agents.pipeline import RESEARCH_TOOLS, ResearchPipelineAgent, extraction_prompt


class PricingAgent(ResearchPipelineAgent):
    definition = AgentDefinition("pricing", "Pricing Intelligence Agent",
                                 "Collects pricing models, plans and prices with source evidence; never infers a missing price.",
                                 ("pricing_models", "subscription_plans", "price_comparison"), RESEARCH_TOOLS)
    dimensions = (("pricing and plans", "pricing", ("pricing", "price", "plan", "subscription")),)
    claim_types = ("pricing",)
    query_suffixes = ("pricing plans", "subscription price per user")
    extract_system = extraction_prompt("pricing", claim_types,
                                       '"company":"","product":"","plan":"","price":"","currency":"","unit":"","pricing_status":"available|unavailable","geography":""',
                                       'If the source says pricing is not published use pricing_status "unavailable" and no price; never estimate a price.')

    def finalize(self, task, claims, md):
        table = {}
        for c in claims:
            a = c["attributes"]
            company = str(a.get("company") or "unknown").strip()
            row = table.setdefault(company, {"plans": [], "pricing_status": "unavailable", "source_ids": []})
            if a.get("price") and a.get("pricing_status") != "unavailable":
                row["plans"].append({"plan": a.get("plan"), "price": a["price"], "currency": a.get("currency"), "claim_id": c["claim_id"]})
                row["pricing_status"] = "available"
            if c["source_id"] not in row["source_ids"]:
                row["source_ids"].append(c["source_id"])
        md["pricing"] = table
