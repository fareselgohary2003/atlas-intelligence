from app.agents.framework import AgentDefinition
from app.agents.pipeline import RESEARCH_TOOLS, ResearchPipelineAgent, extraction_prompt


class RegulationResearchAgent(ResearchPipelineAgent):
    definition = AgentDefinition("regulation", "Regulation & Compliance Research Agent",
                                 "Records what sources state about regulations, licensing and data protection. Provides no legal advice.",
                                 ("regulatory_requirements", "compliance_considerations", "data_protection"), RESEARCH_TOOLS)
    dimensions = (("regulatory requirements", "regulation", ("regulat", "law", "compliance", "licens", "data protection")),)
    claim_types = ("regulation",)
    query_suffixes = ("regulation compliance requirements", "data protection law")
    extract_system = extraction_prompt("regulatory", claim_types,
                                       '"regulator":"","geography":"","period":"","definition":"","population":""',
                                       "State only what the source states about a regulation, who issued it and its scope. Do not interpret the law or give advice.")

    def finalize(self, task, claims, md):
        md["disclaimer"] = "Records what sources state about regulation; this is not legal advice."
