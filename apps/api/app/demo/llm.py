"""Deterministic DEMO LLM. Selected only when DEMO_MODE=true AND LLM_PROVIDER=demo (see services/composition.py).
Invariant: it emits findings ONLY for the fictional mock pages in app/demo/provider.py (reserved '.invalid' URLs), so it can never
fabricate a 'finding' about a real web page. All analysis text is built from the claims it is given."""
import json
import re

from app.agents.state import LLMOutputError
from app.demo.provider import PAGES

U = {k: u for k, u in zip(("size", "growth_a", "growth_b", "acme", "nimbus", "demand", "reg", "risk"), PAGES)}
PLAN = (("market", "Market size and growth of Saudi B2B SaaS"), ("customer", "Customer demand and pain points in Saudi SMB software"),
        ("competitor", "Competitor landscape and pricing for HR software vendors"), ("pricing", "Pricing plans for HR software vendors"),
        ("regulation", "Regulation and data protection compliance requirements"), ("risk", "Risks and adoption barriers for SaaS in Saudi Arabia"))
SA = "Saudi Arabia"


def _f(key, idx, claim, ctype, attrs=None):
    return {"excerpt": PAGES[U[key]][2][idx], "claim": claim, "claim_type": ctype, "stance": "supports", "attributes": attrs or {}}


FINDINGS = {
    U["size"]: [_f("size", 1, "The Saudi Arabia B2B SaaS market was estimated at USD 2.1 billion in 2024", "market_size",
                   {"metric": "market size", "value": 2.1, "unit": "usd billion", "period": "2024", "geography": SA})],
    U["growth_a"]: [_f("growth_a", 1, "The Saudi Arabia B2B SaaS market grew at 18% CAGR between 2022 and 2025 under a narrow definition", "market_growth",
                       {"metric": "market growth", "value": 18, "unit": "percent", "period": "2022-2025", "geography": SA, "definition": "cloud-native SaaS only"})],
    U["growth_b"]: [_f("growth_b", 1, "The Saudi Arabia B2B SaaS market grew at 21% CAGR between 2022 and 2025 under a broad definition", "market_growth",
                       {"metric": "market growth", "value": 21, "unit": "percent", "period": "2022-2025", "geography": SA, "definition": "including managed services"})],
    U["demand"]: [_f("demand", 1, "64% of Saudi medium-sized businesses cite manual reporting as their main pain point", "customer_need",
                     {"metric": "share citing manual reporting", "value": 64, "unit": "percent", "customer_segment": "medium-sized businesses", "geography": SA})],
    U["acme"]: [_f("acme", 1, "AcmeSoft Arabia is a fictional vendor of HR software for medium-sized businesses in Saudi Arabia", "competitor_profile", {"company": "AcmeSoft Arabia"}),
                _f("acme", 2, "AcmeSoft Arabia lists a Team plan at USD 49 per user per month", "pricing",
                   {"company": "AcmeSoft Arabia", "plan": "Team", "price": "49", "currency": "USD", "pricing_status": "available"})],
    U["nimbus"]: [_f("nimbus", 1, "NimbusHR is a fictional vendor targeting enterprise customers in the Gulf region", "competitor_profile", {"company": "NimbusHR"}),
                  _f("nimbus", 2, "NimbusHR does not publish pricing", "pricing", {"company": "NimbusHR", "pricing_status": "unavailable"})],
    U["reg"]: [_f("reg", 1, "The mock Data Protection Regulation requires companies to store personal data of residents inside the Kingdom unless an exemption applies",
                  "regulation", {"regulator": "Mock Data Protection Authority", "geography": SA})],
    U["risk"]: [_f("risk", 1, "Procurement cycles longer than six months are documented as a barrier to SaaS adoption among medium-sized businesses", "risk",
                   {"risk_category": "adoption", "geography": SA})],
}


class DemoLLM:
    name, model = "demo", "demo-deterministic"

    def structured_output(self, system: str, user: str) -> dict:
        if "research planning agent" in system:
            m = re.search(r"one of: ([a-z_, ]+)>", system)
            allowed = {a.strip() for a in m.group(1).split(",")} if m else {a for a, _ in PLAN}
            tasks = [{"id": f"t{i}", "title": t, "agent": a, "depends_on": []} for i, (a, t) in enumerate(PLAN, 1) if a in allowed]
            return {"tasks": tasks}
        if "reviewing progress" in system:
            return {"tasks": []}  # follow-ups come from agents; the demo manager never invents extra work
        if "from ONE source" in system:
            m = re.search(r'"claim_type":"<([a-z_|]+)>"', system)
            allowed = set(m.group(1).split("|")) if m else set()
            url = json.loads(user).get("source_url")
            return {"findings": [f for f in FINDINGS.get(url, []) if f["claim_type"] in allowed]}
        if "You are the analyst" in system:
            return {"items": self._analysis(json.loads(user).get("claims", []))}
        raise LLMOutputError("DemoLLM does not support this prompt")

    @staticmethod
    def _analysis(claims):
        by, claims = {}, sorted(claims, key=lambda c: (c["text"], c["id"]))  # repository order depends on task scheduling: sort for determinism
        for c in claims:
            by.setdefault(c["claim_type"], []).append(c)
        first = lambda t: (by.get(t) or [None])[0]
        items = []
        need, size = first("customer_need"), first("market_size")
        if need and size:
            items.append({"kind": "opportunity", "basis_claim_ids": [need["id"], size["id"]],
                          "text": f'Inference: the claim "{need["text"]}" alongside "{size["text"]}" suggests a possible opportunity for reporting automation aimed at medium-sized businesses.'})
        price, prof = first("pricing"), first("competitor_profile")
        if price and prof:
            items.append({"kind": "opportunity", "basis_claim_ids": [price["id"], prof["id"]],
                          "text": f'Inference: given "{price["text"]}" and "{prof["text"]}", vendors that do not publish pricing may leave room for transparent pricing.'})
        reg = first("regulation")
        if reg:
            items.append({"kind": "risk_inference", "basis_claim_ids": [reg["id"]],
                          "text": f'Inference: "{reg["text"]}" may constrain hosting choices for a new entrant.'})
        for c in [c for c in claims if c["status"] == "partially_supported"][:3]:
            items.append({"kind": "uncertainty", "basis_claim_ids": [c["id"]],
                          "text": f'Uncertainty: "{c["text"]}" is only partially supported ({c["confidence"]} confidence) and should be treated as a lead.'})
        return items
