"""Conflict classification. A numeric difference is a *finding to classify*, not automatically a contradiction:
different periods/geographies/definitions/methodologies/populations are recorded as scope differences."""
from dataclasses import dataclass

from app.evidence.domain import ClaimRecord, digest, norm_text
from app.evidence.verification import cluster_sources

PRECEDENCE = (("period", "different_time_period"), ("geography", "different_geography"),
              ("definition", "different_definition"), ("methodology", "different_methodology"),
              ("population", "different_population"))


@dataclass
class ConflictFinding:
    claim_id: str
    other_claim_id: str | None
    conflict_type: str
    severity: str            # info | low | medium | high
    resolution_status: str   # unresolved | explained_by_scope | needs_review
    explanation: str
    dimensions: dict
    source_a_id: str | None
    source_b_id: str | None
    evidence_a_id: str | None
    evidence_b_id: str | None
    key: str


def _num(c):
    v = c.attributes.get("value")
    return None if isinstance(v, bool) or not isinstance(v, (int, float)) else float(v)


def _attr(c, k):
    v = c.attributes.get(k)
    return norm_text(v) if v not in (None, "") else None


def classify_pair(a: ClaimRecord, b: ClaimRecord, prov_a: dict, prov_b: dict, *, tolerance=.01, direct=.30):
    """prov = {"hashes": set, "source_id": str|None, "evidence_id": str|None}. Returns None when not comparable or in agreement."""
    m = _attr(a, "metric")
    if m is None or m != _attr(b, "metric") or _attr(a, "unit") != _attr(b, "unit"):
        return None
    va, vb = _num(a), _num(b)
    if va is None or vb is None:
        return None
    hi = max(abs(va), abs(vb))
    rel = abs(va - vb) / hi if hi else 0.0
    if rel <= tolerance:
        return None
    lo, top = sorted((va, vb))
    ids = sorted((a.id, b.id))
    mk = lambda t, sev, res, why, dims: ConflictFinding(a.id, b.id, t, sev, res, why, dims, prov_a.get("source_id"),
                                                        prov_b.get("source_id"), prov_a.get("evidence_id"),
                                                        prov_b.get("evidence_id"), digest("pair", t, *ids))
    if prov_a.get("hashes", set()) & prov_b.get("hashes", set()):
        return mk("duplicate_or_derived_source", "low", "needs_review",
                  f"Both figures for '{m}' trace to the same or a derived source; likely an extraction inconsistency, not independent evidence.", {})
    differing = {k: [a.attributes[k], b.attributes[k]] for k, _ in PRECEDENCE
                 if _attr(a, k) and _attr(b, k) and _attr(a, k) != _attr(b, k)}
    if differing:
        ctype = next(t for k, t in PRECEDENCE if k in differing)
        return mk(ctype, "info", "explained_by_scope",
                  f"Values for '{m}' ({va:g} vs {vb:g}) differ in {', '.join(differing)}; the figures are not like-for-like, so this is not a contradiction.", differing)
    unspecified = [k for k, _ in PRECEDENCE if bool(_attr(a, k)) != bool(_attr(b, k))]
    both_known = all(_attr(a, k) and _attr(b, k) for k in ("period", "geography"))
    sev = "low" if rel < .10 else "medium"
    if both_known and rel >= direct:
        return mk("direct_contradiction", "high", "unresolved",
                  f"Sources report incompatible values for '{m}' ({va:g} vs {vb:g}) for the same stated period and geography.", {})
    note = "" if both_known else " Period or geography is not stated on both sides, so scope differences cannot be ruled out."
    return mk("numerical_disagreement", sev, "unresolved" if both_known else "needs_review",
              f"Available sources estimate '{m}' between {lo:g} and {top:g}; differences may reflect definitions or methodology.{note}",
              {"unspecified": unspecified} if unspecified else {})


def stance_conflicts(claim: ClaimRecord, stanced) -> list:
    """Independent sources that support AND contradict the same claim. Sources are clustered across BOTH sides first, so a
    publisher (or copy of a source) that appears on both sides is treated as internally inconsistent, not as an independent dispute."""
    side = {e.id: st for e, _, st in stanced if st in ("supports", "contradicts")}
    clusters = cluster_sources([(e, s) for e, s, st in stanced if st in ("supports", "contradicts")])
    sc = [c for c in clusters if {side[e.id] for e, _ in c} == {"supports"}]
    cc = [c for c in clusters if {side[e.id] for e, _ in c} == {"contradicts"}]
    if not sc or not cc:
        return []
    (ea, sa), (eb, sb) = sc[0][0], cc[0][0]
    return [ConflictFinding(claim.id, None, "direct_contradiction", "high", "unresolved",
                            f"{len(sc)} independent source(s) support and {len(cc)} contradict this claim.", {},
                            sa.id, sb.id, ea.id, eb.id, digest("stance", claim.id, "direct_contradiction"))]
