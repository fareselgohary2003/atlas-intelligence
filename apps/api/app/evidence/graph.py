"""Evidence graph from stored records only: Claim -> Evidence -> Source, and Claim <-> Claim conflicts."""


def build_graph(claims, evidence, sources, conflicts, limit=200) -> dict:
    cl = sorted(claims, key=lambda c: (c.created_at, c.id))
    truncated = len(cl) > limit
    cl = cl[:limit]
    ids = {c.id for c in cl}
    src = {s.id: s for s in sources}
    stance_conflict = {c.claim_id for c in conflicts if c.other_claim_id is None}
    nodes, edges, used_src = [], [], set()
    for c in cl:
        nodes.append({"id": f"c:{c.id}", "type": "claim", "label": c.text[:140], "status": c.status, "confidence": c.confidence,
                      "claim_type": c.claim_type, "is_demo": c.is_demo, "has_conflict": c.id in stance_conflict or any(x.claim_id == c.id or x.other_claim_id == c.id for x in conflicts)})
    for e in sorted(evidence, key=lambda e: (e.created_at, e.id)):
        if e.claim_id not in ids or e.source_id not in src:
            continue
        nodes.append({"id": f"e:{e.id}", "type": "evidence", "label": e.excerpt[:120], "stance": e.stance, "quality": (e.quality or {}).get("level"), "is_demo": e.is_demo})
        edges.append({"id": f"ce:{e.id}", "source": f"c:{e.claim_id}", "target": f"e:{e.id}", "type": "has_evidence", "stance": e.stance})
        edges.append({"id": f"es:{e.id}", "source": f"e:{e.id}", "target": f"s:{e.source_id}", "type": "from_source"})
        used_src.add(e.source_id)
    for sid in sorted(used_src):
        s = src[sid]
        nodes.append({"id": f"s:{sid}", "type": "source", "label": s.title or s.domain, "url": s.url, "source_type": s.source_type, "publisher": s.publisher, "is_demo": s.is_demo})
    for x in conflicts:
        if x.other_claim_id and x.claim_id in ids and x.other_claim_id in ids:
            edges.append({"id": f"cc:{x.id}", "source": f"c:{x.claim_id}", "target": f"c:{x.other_claim_id}", "type": "conflicts_with",
                          "conflict_type": x.conflict_type, "severity": x.severity, "resolution_status": x.resolution_status})
    return {"nodes": nodes, "edges": edges, "truncated": truncated,
            "counts": {"claims": len(cl), "evidence": sum(n["type"] == "evidence" for n in nodes), "sources": len(used_src),
                       "conflicts": sum(e["type"] == "conflicts_with" for e in edges)}}
