from app.agents.framework import AgentDefinition
from app.agents.pipeline import RESEARCH_TOOLS, ResearchPipelineAgent, extraction_prompt


class RiskAgent(ResearchPipelineAgent):
    definition = AgentDefinition("risk", "Risk Research Agent",
                                 "Identifies market, competitive, regulatory, adoption, pricing and operational risks that sources document.",
                                 ("market_risks", "competitive_risks", "regulatory_risks", "adoption_risks"), RESEARCH_TOOLS)
    dimensions = (("documented risks and barriers", "risk", ("risk", "threat", "barrier", "challenge")),)
    claim_types = ("risk",)
    query_suffixes = ("risks barriers challenges", "adoption barriers")
    extract_system = extraction_prompt("risk", claim_types,
                                       '"risk_category":"market|competitive|regulatory|adoption|pricing|operational","geography":"","period":""',
                                       "Record only risks the source itself states; do not add your own assessment of likelihood or impact.")
