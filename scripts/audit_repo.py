#!/usr/bin/env python3
"""Repository hygiene audit: placeholder markers and unused imports. Intentional demo/test code is classified, not hidden."""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARK = re.compile(r"\b(TODO|FIXME|NotImplemented\w*|placeholder|stub|temporary|temporarily|fake|mock|HACK|XXX)\b", re.I)
SKIP = {"node_modules", "__pycache__", ".next", ".git"}
files = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".mjs", ".yml", ".md", ".sh") and not (SKIP & set(p.parts))]
INTENTIONAL_LINE = re.compile(r"placeholder=|placeholder:|<Mock|\bMock\b|MOCK|DEMO_BANNER|fictional mock|never replaced with fake output|temporarily unavailable|\[MOCK\]", re.I)
intentional = lambda p: "tests" in p.parts or "demo" in p.parts or p.name in ("UNVERIFIED.md", "DEMO.md", "TESTING.md", "SECURITY.md", "audit_repo.py", "README.md", "AGENTS.md", "EVIDENCE.md", "ARCHITECTURE.md", "TOOLS.md", "SETUP.md", "API.md")
flag, ok = [], 0
for p in files:
    for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
        if MARK.search(line):
            (ok := ok + 1) if intentional(p) or INTENTIONAL_LINE.search(line) else flag.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:110]}")
print(f"placeholder markers in intentional demo/test/doc files: {ok}")
print(f"placeholder markers needing review: {len(flag)}")
print(*flag, sep="\n")
unused = []
for p in files:
    if p.suffix != ".py" or p.name == "__init__.py":
        continue
    src = p.read_text()
    tree = ast.parse(src)
    imported = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                imported[(a.asname or a.name).split(".")[0]] = n.lineno
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                imported[a.asname or a.name] = n.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    lines = src.splitlines()
    for name, ln in imported.items():
        if name not in used and "noqa" not in lines[ln - 1] and name != "annotations" and f'"{name}"' not in src:
            unused.append(f"{p.relative_to(ROOT)}:{ln}: unused import {name}")
print(f"unused imports: {len(unused)}")
print(*unused, sep="\n")
sys.exit(1 if flag or unused else 0)
