from datetime import datetime, timedelta, timezone

from app.evidence.domain import ClaimRecord, EvidenceRecord, SourceRecord
from app.evidence.verification import evidence_quality

NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)
_n = iter(range(1, 10_000))


def src(domain="a.example", stype="other", years=1.0, h=None, rid="r1"):
    i = next(_n)
    pub = None if years is None else NOW - timedelta(days=365 * years)
    return SourceRecord(f"s{i}", rid, "w1", f"https://{domain}/{i}", f"https://{domain}/{i}", domain, "T", domain, pub, NOW, stype,
                        h or f"hash{i}", None, {}, [], False, NOW)


def claim(text="The market reached USD 2.1 billion in 2024", value=2.1, rid="r1", cid=None, **attrs):
    i = next(_n)
    a = {"metric": "market size", "unit": "usd billion", **attrs}
    if value is not None:
        a["value"] = value
    return ClaimRecord(cid or f"c{i}", rid, "w1", text, "market_size", "proposed", "UNVERIFIED", a, "market", "t1", f"k{i}", False, NOW, NOW)


def ev(source, claim_rec, stance="supports", excerpt="Market size hit USD 2.1 billion in 2024.", rid="r1"):
    i = next(_n)
    return EvidenceRecord(f"e{i}", rid, "w1", source.id, claim_rec.id, "t1", "market", excerpt, {"start": 0}, stance,
                          evidence_quality(source, excerpt, claim_rec.attributes, True, NOW), {}, f"ek{i}", False, NOW)
