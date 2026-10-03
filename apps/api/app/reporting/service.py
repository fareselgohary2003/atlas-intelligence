"""ReportService: builds an immutable, versioned report from stored records and serves exports of a stored version."""
from dataclasses import dataclass
from typing import Protocol

from app.evidence.domain import DuplicateError, EvidenceError, Scope, new_id, now
from app.reporting.builder import ReportInputs, build_report
from app.reporting.export import FORMATS, to_json, to_markdown, to_pdf


@dataclass
class ReportRecord:
    id: str
    research_id: str
    workspace_id: str
    version: int
    title: str
    is_demo: bool
    content: dict
    created_at: object


class ReportInputsProvider(Protocol):
    def research(self, research_id: str) -> dict | None: ...   # includes workspace_id and is_demo
    def snapshot(self, research_id: str, at) -> ReportInputs: ...


class ReportRepository(Protocol):
    def add_report(self, rec: ReportRecord, audit_hook=None) -> None: ...  # DuplicateError on (research, version) clash; audit_hook(db, rec) runs in the same transaction, only on success
    def latest_report(self, research_id: str) -> ReportRecord | None: ...
    def get_report(self, research_id: str, version: int) -> ReportRecord | None: ...
    def list_versions(self, research_id: str) -> list: ...  # [{version, id, title, is_demo, created_at}] newest first


class ReportService:
    def __init__(self, inputs: ReportInputsProvider, repo: ReportRepository, clock=now):
        self.inputs, self.repo, self.clock = inputs, repo, clock

    def _check(self, scope: Scope) -> dict:
        r = self.inputs.research(scope.research_id)
        if r is None or str(r["workspace_id"]) != str(scope.workspace_id):
            raise EvidenceError("not_found", "Research not found in this workspace")
        return r

    def generate(self, scope: Scope, audit_hook=None) -> ReportRecord:
        self._check(scope)
        at = self.clock()
        report = build_report(self.inputs.snapshot(scope.research_id, at))
        for _ in range(3):  # a concurrent generation may take our version number: retry with the next one
            latest = self.repo.latest_report(scope.research_id)
            rec = ReportRecord(new_id(), scope.research_id, scope.workspace_id, (latest.version + 1) if latest else 1,
                               report["title"], report["is_demo"], report, at)
            try:
                self.repo.add_report(rec, audit_hook)
                return rec
            except DuplicateError:
                continue
        raise EvidenceError("conflict", "Could not allocate a report version; try again")

    def versions(self, scope: Scope) -> list:
        self._check(scope)
        return self.repo.list_versions(scope.research_id)

    def get(self, scope: Scope, version: int | None = None) -> ReportRecord:
        self._check(scope)
        rec = self.repo.latest_report(scope.research_id) if version is None else self.repo.get_report(scope.research_id, version)
        if rec is None:
            raise EvidenceError("not_found", "Report not found")
        return rec

    def export(self, scope: Scope, fmt: str, version: int | None = None):
        """Returns (payload, content_type, filename). Read-only: renders the stored report, never re-reads or changes research records."""
        if fmt not in FORMATS:
            raise EvidenceError("invalid", f"Unsupported export format; choose one of {', '.join(FORMATS)}")
        rec = self.get(scope, version)
        stem = f"atlas-report-v{rec.version}"
        if fmt == "md":
            return to_markdown(rec.content), "text/markdown; charset=utf-8", stem + ".md"
        if fmt == "json":
            return to_json(rec.content), "application/json", stem + ".json"
        return to_pdf(rec.content), "application/pdf", stem + ".pdf"
