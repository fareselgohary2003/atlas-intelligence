from app.agents.framework import AgentDefinition
from app.agents.pipeline import ResearchPipelineAgent

TOOLS = ("web_search", "fetch_url", "extract_page_content", "save_source", "create_claim", "create_evidence", "request_research", "update_task")


class MarketResearchAgent(ResearchPipelineAgent):
    definition = AgentDefinition("market", "Market Research Agent",
                                 "Investigates market size, growth, segments and adoption from retrieved sources.",
                                 ("market_size", "market_growth", "market_segments", "adoption_trends"), TOOLS)
    dimensions = (("market size", "market_size", ("size", "tam", "sam", "value")),
                  ("market growth", "market_growth", ("growth", "cagr")),
                  ("market segments", "market_segment", ("segment",)),
                  ("adoption trends", "adoption", ("adoption", "trend")))
    claim_types = ("market_size", "market_growth", "market_segment", "trend", "adoption")
    query_suffixes = ("market size report", "growth rate CAGR")
    extract_system = (
        "You extract evidence for a market research task from ONE source. Return ONLY JSON: "
        '{"findings":[{"excerpt":"<text copied EXACTLY from the source>","claim":"<one factual statement the excerpt supports>",'
        '"claim_type":"<market_size|market_growth|market_segment|trend|adoption>","stance":"supports|contradicts",'
        '"attributes":{"metric":"","value":<number exactly as written>,"unit":"","period":"","geography":"","definition":"","methodology":"","population":""}}]}. '
        "Rules: copy excerpts verbatim; never estimate, compute or convert numbers; omit attributes the source does not state; "
        'if nothing relevant is present return {"findings":[]}.')
