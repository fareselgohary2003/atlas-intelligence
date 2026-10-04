"""Exports are pure renderings of a stored report; they never touch research records."""
import csv
import io
import json

FORMATS = ("md", "json", "pdf", "csv")


def _cites(ns):
    return "".join(f"[{n}]" for n in ns)


def to_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str)


def to_markdown(report: dict) -> str:
    out = [f"# {report['title']}", ""]
    if report.get("provenance"):
        out += [f"> **{report['provenance']}**", ""]
    out += [f"_Generated {report['generated_at']}_", ""]
    for i, s in enumerate(report["sections"], 1):
        out += [f"## {i}. {s['title']}", ""]
        if s["key"] == "sources":
            out += [f"[{c['n']}] {c['title'] or c['url']} - {c['publisher']}, {c['url']} (published {c['published_at'] or 'n/a'}, retrieved {c['retrieved_at']})"
                    + (" **[DEMO]**" if c["is_demo"] else "") + "  " for c in report["citations"]] + [""]
        for p in s.get("paragraphs", []):
            out += [(f"*{p['text']}*" if p["kind"] in ("gap", "note") else p["text"]), ""]
        for f in s.get("findings", []):
            out += [f"- **{f['label']}** ({f['confidence']}) {f['text']} {_cites(f['citations'])}"]
            if s["key"] == "claims_appendix":
                out += [f"  - evidence [{e['n']}]: \"{e['excerpt']}\"" for e in f["evidence"]]
            elif f.get("rationale"):
                out += [f"  - {f['rationale']}"]
        for a in s.get("analysis", []):
            out += [f"- **{a['label']}** {a['text']} {_cites(a['citations'])}"] + [f"  - basis ({b['label']}): {b['text']} {_cites(b['citations'])}" for b in a["basis"]]
        for c in s.get("conflicts", []):
            a, b = c["claim_a"], c.get("claim_b")
            out += [f"- **{c['conflict_type'].replace('_', ' ')}** ({c['severity']}, {c['resolution_status'].replace('_', ' ')}): {c['explanation']}",
                    f"  - A: {a['text']} {_cites(a['citations'])}"] + ([f"  - B: {b['text']} {_cites(b['citations'])}"] if b else [])
        out.append("")
    return "\n".join(out).rstrip() + "\n"


_INJECTION_CHARS = ("=", "+", "-", "@")  # spreadsheet formula injection characters


def _csv_safe(value: object) -> str:
    """Prevent spreadsheet formula injection by prefixing dangerous leading characters with a tab."""
    s = "" if value is None else str(value)
    if s and s[0] in _INJECTION_CHARS:
        s = "\t" + s
    return s


def to_csv(report: dict) -> bytes:
    """Export findings as a UTF-8 CSV (BOM included for Excel compatibility).
    Each row is one evidence-backed finding. Claims without evidence are listed in a trailing summary row.
    Injection-safe: cells that would start a spreadsheet formula are prefixed with a tab character."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow([
        "Section", "Claim", "Type", "Status", "Confidence",
        "Citations", "Rationale", "Is Demo",
        "Metric", "Value", "Unit", "Period", "Geography",
    ])
    for s in report.get("sections", []):
        if s.get("key") in ("sources", "claims_appendix", "gaps", "conclusion", "methodology", "objective"):
            continue
        for f in s.get("findings", []):
            attrs = f.get("attributes", {})
            writer.writerow([
                _csv_safe(s.get("title")),
                _csv_safe(f.get("text")),
                _csv_safe(f.get("claim_type")),
                _csv_safe(f.get("status")),
                _csv_safe(f.get("confidence")),
                _csv_safe(", ".join(f"[{n}]" for n in f.get("citations", []))),
                _csv_safe(f.get("rationale")),
                _csv_safe("YES" if f.get("is_demo") else "NO"),
                _csv_safe(attrs.get("metric")),
                _csv_safe(attrs.get("value")),
                _csv_safe(attrs.get("unit")),
                _csv_safe(attrs.get("period")),
                _csv_safe(attrs.get("geography")),
            ])
    # Trailing sources reference sheet
    if report.get("citations"):
        writer.writerow([])  # blank separator
        writer.writerow(["[n]", "Title", "Publisher", "URL", "Source Type", "Published", "Retrieved", "Is Demo"])
        for c in report["citations"]:
            writer.writerow([
                _csv_safe(f"[{c['n']}]"),
                _csv_safe(c.get("title") or c.get("url")),
                _csv_safe(c.get("publisher")),
                _csv_safe(c.get("url")),
                _csv_safe(c.get("source_type")),
                _csv_safe(c.get("published_at") or "n/a"),
                _csv_safe(c.get("retrieved_at")),
                _csv_safe("YES" if c.get("is_demo") else "NO"),
            ])
    # Return UTF-8 with BOM for Microsoft Excel compatibility
    return "\ufeff".encode("utf-8") + buf.getvalue().encode("utf-8")


def _lines(report: dict) -> list:
    return [l for l in to_markdown(report).replace("**", "").replace("*", "").replace("> ", "").replace("_", "").replace("#", "").split("\n")]


def to_pdf(report: dict) -> bytes:
    """Minimal text-only PDF (Helvetica, Latin-1). Non-Latin-1 characters become '?'. Structure is tested; visual rendering is not."""
    W, LINE, TOP, LEFT, PER_PAGE, WRAP = 595, 14, 800, 50, 52, 92
    lines = []
    for raw in _lines(report):
        raw = raw.encode("latin-1", "replace").decode("latin-1")
        while len(raw) > WRAP:
            cut = raw.rfind(" ", 0, WRAP) or WRAP
            cut = cut if cut > 0 else WRAP
            lines.append(raw[:cut])
            raw = "  " + raw[cut:].lstrip()
        lines.append(raw)
    pages = [lines[i:i + PER_PAGE] for i in range(0, len(lines), PER_PAGE)] or [[""]]
    esc = lambda t: t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    kids = []
    for pg in pages:
        body = "BT /F1 9 Tf %d TL %d %d Td\n" % (LINE, LEFT, TOP) + "".join(f"({esc(l)}) '\n" for l in pg) + "ET"
        content = body.encode("latin-1")
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        cid = len(objs)
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d 842] /Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (W, cid))
        kids.append(len(objs))
    objs[1] = ("<< /Type /Pages /Count %d /Kids [%s] >>" % (len(pages), " ".join(f"{k} 0 R" for k in kids))).encode()
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)
