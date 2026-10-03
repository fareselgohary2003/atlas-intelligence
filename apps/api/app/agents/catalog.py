"""Single source of truth for the agent set (used by composition and by the agents API)."""
from app.agents.analyst import AnalystAgent
from app.agents.competitor import CompetitorResearchAgent
from app.agents.customer import CustomerResearchAgent
from app.agents.factchecker import FactCheckerAgent
from app.agents.framework import AgentDefinition
from app.agents.market import MarketResearchAgent
from app.agents.pricing import PricingAgent
from app.agents.regulation import RegulationResearchAgent
from app.agents.risk import RiskAgent

AGENT_CLASSES = (MarketResearchAgent, CustomerResearchAgent, CompetitorResearchAgent, PricingAgent, RegulationResearchAgent, RiskAgent,
                 FactCheckerAgent, AnalystAgent)
MANAGER = AgentDefinition("research_manager", "Research Manager",
                          "Plans the research, schedules verification and analysis, and turns evidence gaps and conflicts into follow-up tasks (bounded by max_replans).",
                          ("planning", "replanning", "gap_detection", "delegation"), ())


def agent_definitions() -> list:
    return [MANAGER] + [c.definition for c in AGENT_CLASSES]
