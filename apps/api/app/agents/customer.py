from app.agents.framework import AgentDefinition
from app.agents.pipeline import RESEARCH_TOOLS, ResearchPipelineAgent, extraction_prompt


class CustomerResearchAgent(ResearchPipelineAgent):
    definition = AgentDefinition("customer", "Customer & Demand Research Agent",
                                 "Investigates customer needs, pain points and demand signals with source evidence.",
                                 ("customer_needs", "demand_signals", "buying_behavior"), RESEARCH_TOOLS)
    dimensions = (("customer needs and pain points", "customer_need", ("pain", "need", "customer", "buyer")),
                  ("demand and adoption signals", "adoption", ("demand", "adoption", "intent")))
    claim_types = ("customer_need", "adoption", "trend")
    query_suffixes = ("customer needs pain points", "demand adoption survey")
    extract_system = extraction_prompt("customer and demand", claim_types,
                                       '"metric":"","value":<number as written>,"unit":"","customer_segment":"","geography":"","period":"","population":"","methodology":""',
                                       "Record survey figures only with their stated population and methodology when present.")
