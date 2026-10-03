"""Deterministic verification + transparent evidence-quality scoring. An LLM judge is optional and only refines
stance; it is never consulted when the deterministic checks already show the evidence is insufficient."""
import re
from dataclasses import dataclass
from datetime import datetime
from statistics import mean

from app.evidence.domain import ClaimRecord, SourceRecord, now

AUTHORITY = {"government": .9, "academic": .85, "research": .8, "company": .6, "news": .6, "forum": .3, "other": .4}
WEIGHTS = {"authority": .25, "recency": .15, "directness": .20, "specificity": .10, "extraction": .10,
           "independence": .10, "corroboration": .10}
EVIDENCE_LEVEL = ("authority", "recency", "directness", "specificity", "extraction")
ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
FRESH_YEARS = 5


def level(x: float) -> str:
    return "HIGH" if x >= .75 else "MEDIUM" if x >= .5 else "LOW"


def cap(conf: str, ceiling: str) -> str:
    return conf if ORDER.get(conf, 0) <= ORDER[ceiling] else ceiling


def numbers_in(text: str) -> list:
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", re.sub(r"(?<=\d),(?=\d{3}\b)", "", text))]


def number_in_text(value, text: str) -> bool:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return any(abs(n - v) <= 1e-9 * max(1.0, abs(v)) for n in numbers_in(text))


def _age(published: datetime | None, at: datetime):
    return None if published is None else (at - (published if published.tzinfo else published.replace(tzinfo=at.tzinfo))).days / 365.25


def evidence_quality(source: SourceRecord, excerpt: str, attributes: dict, grounded: bool, at: datetime | None = None) -> dict:
    """Per-evidence factors. Heuristic and explainable: every score carries its reason; the total is a weighted mean."""
    at = at or now()
    age = _age(source.published_at, at)
    rec = (.3, "publication date unknown") if age is None else next(
        (s, f"published {age:.1f} years ago") for lim, s in ((1, 1.0), (2, .8), (3, .6), (5, .4), (999, .2)) if age <= lim)
    val = attributes.get("value")
    direct = (.6, "no numeric value to check") if val is None else \
        (1.0, "excerpt states the claimed value") if number_in_text(val, excerpt) else (.3, "claimed value not in excerpt")
    comps = {"authority": (AUTHORITY.get(source.source_type, .4), f"source_type={source.source_type} (heuristic table)"),
             "recency": rec, "directness": direct,
             "specificity": (.8, "contains figures") if re.search(r"\d", excerpt) else (.5, "no figures"),
             "extraction": (1.0, "excerpt located verbatim in stored source text") if grounded else (.3, "could not be checked against source text")}
    total = sum(WEIGHTS[k] * comps[k][0] for k in EVIDENCE_LEVEL) / sum(WEIGHTS[k] for k in EVIDENCE_LEVEL)
    return {"components": {k: {"score": v[0], "note": v[1]} for k, v in comps.items()}, "total": round(total, 3),
            "level": level(total), "weights": {k: WEIGHTS[k] for k in EVIDENCE_LEVEL}}


class LLMEntailmentJudge:
    """Optional judge: does this excerpt support / contradict / not relate to the claim? Output is validated by the caller."""
    SYSTEM = ('Judge whether the excerpt supports the claim. Return ONLY JSON {"verdict":"supports|contradicts|unrelated",'
              '"note":"<=200 chars"}. Use only the excerpt; add no outside facts.')

    def __init__(self, llm):
        self.llm = llm

    def assess(self, claim_text: str, excerpt: str) -> dict:
        import json
        return self.llm.structured_output(self.SYSTEM, json.dumps({"claim": claim_text, "excerpt": excerpt}))


@dataclass
class VerificationOutcome:
    outcome: str
    confidence: str
    rationale: str
    evidence_ids: list
    factors: dict
    verifier: str = "rules/1"


def cluster_sources(pairs):
    """Independence: sources sharing content or a publisher domain count once."""
    by_hash, by_domain, clusters = {}, {}, []
    for ev, src in pairs:
        c = by_hash.get(src.content_hash)
        c = by_domain.get(src.domain) if c is None else c
        if c is None:
            c = len(clusters)
            clusters.append([])
        by_hash[src.content_hash] = by_domain[src.domain] = c
        clusters[c].append((ev, src))
    return clusters


def assess_stances(claim: ClaimRecord, evidence: list, sources: dict, judge=None):
    """Integrity checks, then (optionally) an LLM judge. Returns ([(ev, src, stance)], issues, notes)."""
    issues, notes, out = [], [], []
    for ev in evidence:
        src = sources.get(ev.source_id)
        if ev.research_id != claim.research_id:
            issues.append("evidence_wrong_research")
        elif src is None or src.research_id != claim.research_id:
            issues.append("source_missing")
        elif not ev.excerpt.strip():
            issues.append("empty_excerpt")
        else:
            stance = ev.stance
            if judge is not None:
                try:
                    j = judge.assess(claim.text, ev.excerpt)
                    v = j.get("verdict") if isinstance(j, dict) else None
                except Exception:
                    v = None
                if v in ("supports", "contradicts", "unrelated"):
                    stance = "context" if v == "unrelated" else v
                else:
                    notes.append("judge_unavailable_for_some_evidence")
            out.append((ev, src, stance))
    return out, issues, sorted(set(notes))


def _claim_quality(items, n_clusters):
    quals = [ev.quality for ev, _ in items if ev.quality.get("components")]
    comps = {k: round(mean(q["components"][k]["score"] for q in quals), 3) for k in EVIDENCE_LEVEL} if quals else {}
    comps["independence"] = round(n_clusters / max(1, len(items)), 3)
    comps["corroboration"] = round(min(1.0, n_clusters / 2), 3)
    total = sum(WEIGHTS[k] * v for k, v in comps.items()) / sum(WEIGHTS[k] for k in comps)
    return round(total, 3), comps


def verify_stanced(claim, stanced, issues=(), notes=(), *, at=None, open_conflicts=(), verifier="rules/1") -> VerificationOutcome:
    at = at or now()
    factors = {"issues": list(issues), "notes": list(notes)}
    if not stanced:
        msg = "No valid evidence is linked to this claim." + (f" Problems found: {', '.join(sorted(set(issues)))}." if issues else "")
        return VerificationOutcome("insufficient_evidence", "UNVERIFIED", msg, [], factors, verifier)
    sup = [(e, s) for e, s, st in stanced if st == "supports"]
    con = [(e, s) for e, s, st in stanced if st == "contradicts"]
    val = claim.attributes.get("value")
    if sup and val is not None and not any(number_in_text(val, e.excerpt) for e, _ in sup):
        factors["ungrounded_value"] = val  # the stated number is not in any supporting excerpt
        sup = []
    sc, cc = cluster_sources(sup), cluster_sources(con)
    S, C = len(sc), len(cc)
    ids = [e.id for e, _, _ in stanced]
    if S == 0 and C == 0:
        why = "The stated value does not appear in any supporting excerpt." if "ungrounded_value" in factors else \
            "The linked evidence neither supports nor contradicts the claim."
        return VerificationOutcome("insufficient_evidence", "UNVERIFIED", why, ids, factors, verifier)
    side, n = (sup, S) if S else (con, C)
    total, comps = _claim_quality(side, n)
    factors.update({"independent_supporting": S, "independent_contradicting": C, "components": comps, "total": total,
                    "weights": {k: WEIGHTS[k] for k in comps}})
    conf = level(total)
    dup = len(side) - n
    dup_note = f" {dup} additional source(s) share content or publisher and count once." if dup else ""
    if S == 0:
        return VerificationOutcome("contradicted", conf, f"{C} independent source(s) contradict the claim and none support it.{dup_note}", ids, factors, verifier)
    fresh = any((_age(s.published_at, at) or 99) <= FRESH_YEARS for _, s in sup)
    if not fresh:
        conf, factors["freshness"] = cap(conf, "LOW"), f"no supporting source is dated within {FRESH_YEARS} years"
    if C:
        return VerificationOutcome("partially_supported", cap(conf, "LOW"),
                                   f"Contested: {S} independent source(s) support and {C} contradict this claim.{dup_note}", ids, factors, verifier)
    if any(c.conflict_type == "direct_contradiction" and c.resolution_status == "unresolved" for c in open_conflicts):
        return VerificationOutcome("partially_supported", cap(conf, "LOW"),
                                   f"{S} independent source(s) support the claim, but an unresolved direct contradiction exists.{dup_note}", ids, factors, verifier)
    if S >= 2:
        return VerificationOutcome("supported", conf, f"{S} independent sources support the claim.{dup_note}", ids, factors, verifier)
    e, s = sup[0]
    strong = comps["authority"] >= .8 and comps["directness"] >= .8
    if strong:
        return VerificationOutcome("supported", cap(conf, "MEDIUM"), f"One authoritative, direct source supports the claim; no corroboration.{dup_note}", ids, factors, verifier)
    return VerificationOutcome("partially_supported", cap(conf, "LOW"), f"Only one independent source supports the claim and it is not both authoritative and direct.{dup_note}", ids, factors, verifier)


def verify(claim, evidence, sources, *, judge=None, at=None, open_conflicts=()) -> VerificationOutcome:
    stanced, issues, notes = assess_stances(claim, evidence, sources, judge)
    return verify_stanced(claim, stanced, issues, notes, at=at, open_conflicts=open_conflicts,
                          verifier="rules+judge/1" if judge else "rules/1")
