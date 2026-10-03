"""DEMO / MOCK corpus. Everything here is fictional test content on the reserved '.invalid' TLD (RFC 2606) so it can never be a
real URL. Selected only when DEMO_MODE=true AND WEB_SEARCH_PROVIDER=demo; never a fallback for missing credentials."""
import re
from datetime import datetime, timezone

from app.tools.base import ToolError
from app.tools.extract import parse_date
from app.tools.fetch import FetchResult
from app.tools.search import SearchOptions, SearchResult
from app.tools.sources import domain_of

BANNER = "MOCK / DEMO DATA - this page is fictional test content, not a real publication."
PAGES = {  # url -> (title, published, sentences); sentence index 1 carries the key (mock) fact
    "https://analyst-one.mock.invalid/saudi-saas-market-size": ("Saudi B2B SaaS Market Size (MOCK)", "2026-02-10", [
        BANNER, "The Saudi Arabia B2B SaaS market was estimated at USD 2.1 billion in 2024 in this mock analyst note.",
        "The estimate covers subscription software sold to medium-sized businesses across the Kingdom.",
        "All figures on this page are invented for software testing only and describe no real market."]),
    "https://analyst-two.mock.invalid/saudi-saas-growth": ("Saudi B2B SaaS Growth, narrow definition (MOCK)", "2026-03-01", [
        BANNER, "The Saudi Arabia B2B SaaS market grew at 18% CAGR between 2022 and 2025 under a narrow definition limited to cloud-native SaaS.",
        "This mock analyst excludes managed services and on-premise software from its market boundary.",
        "All figures on this page are invented for software testing only and describe no real market."]),
    "https://analyst-three.mock.invalid/saudi-saas-growth": ("Saudi B2B SaaS Growth, broad definition (MOCK)", "2026-03-15", [
        BANNER, "The Saudi Arabia B2B SaaS market grew at 21% CAGR between 2022 and 2025 under a broad definition that includes managed services.",
        "This mock analyst counts hosted and managed software offerings inside its market boundary.",
        "All figures on this page are invented for software testing only and describe no real market."]),
    "https://vendors.mock.invalid/acmesoft-arabia": ("AcmeSoft Arabia (MOCK vendor profile)", "2026-01-20", [
        BANNER, "AcmeSoft Arabia is a fictional vendor of HR software for medium-sized businesses in Saudi Arabia.",
        "AcmeSoft Arabia lists a Team plan at USD 49 per user per month on its mock price sheet.",
        "This vendor does not exist; the profile is generated test content."]),
    "https://vendors.mock.invalid/nimbushr": ("NimbusHR (MOCK vendor profile)", "2026-01-22", [
        BANNER, "NimbusHR is a fictional vendor targeting enterprise customers in the Gulf region.",
        "NimbusHR does not publish pricing and asks customers to contact sales for a quote.",
        "This vendor does not exist; the profile is generated test content."]),
}
PAGES.update({
    "https://research.mock.invalid/saudi-sme-demand": ("SME software demand survey (MOCK)", "2026-02-20", [
        BANNER, "In this mock survey 64% of Saudi medium-sized businesses said manual reporting is their main pain point.",
        "The mock survey sample is fictional and was generated for software testing only.",
        "No real respondents exist behind these figures."]),
    "https://regulator.mock.invalid/data-protection": ("Data Protection Regulation summary (MOCK)", "2026-01-15", [
        BANNER, "The mock Data Protection Regulation requires companies to store personal data of residents inside the Kingdom unless an exemption applies.",
        "This fictional regulation is described here only to test regulatory research.",
        "It is not a real law and must not be relied on."]),
    "https://risk.mock.invalid/adoption-barriers": ("SaaS adoption barriers (MOCK)", "2026-02-01", [
        BANNER, "Mock analysts list procurement cycles longer than six months as a barrier to SaaS adoption among medium-sized businesses.",
        "These barriers are fictional and were generated for software testing only.",
        "No real analyst holds these views."]),
})
FETCHED_AT = datetime(2026, 9, 30, tzinfo=timezone.utc)


def _html(title, published, sents):
    return (f'<html lang="en"><head><title>{title}</title><meta property="article:published_time" content="{published}">'
            f'<meta property="og:site_name" content="MOCK"></head><body><article>' + "".join(f"<p>{s}</p>" for s in sents) + "</article></body></html>")


STOP = {"and", "for", "the", "with", "from", "that", "this", "are", "was", "how", "what", "into", "about"}


def _stem(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") else w  # crude plural folding, deterministic


class DemoSearchProvider:
    name = "demo"

    def search(self, query, options: SearchOptions):
        words = {_stem(w) for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2 and w not in STOP}
        scored = []
        for url, (title, pub, sents) in PAGES.items():
            t_hay, hay = title.lower(), " ".join(sents).lower()
            score = sum(2 * (w in t_hay) + (w in hay) for w in words)  # title matches weigh double
            if score:
                scored.append((-score, url, title, pub, sents[1]))
        return [SearchResult(t, u, snip, domain_of(u), parse_date(p), i + 1, {"is_demo": True})
                for i, (_, u, t, p, snip) in enumerate(sorted(scored)[:options.count])]


class DemoFetcher:
    """Serves the mock corpus; performs no network access."""
    def fetch(self, url, cancel=None):
        if url not in PAGES:
            raise ToolError("upstream", "Server responded with HTTP 404")
        title, pub, sents = PAGES[url]
        html = _html(title, pub, sents)
        return FetchResult(url, 200, "text/html", html, len(html), [], FETCHED_AT)
