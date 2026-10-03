import unittest

from app.evidence.domain import DuplicateError
from app.evidence.service import EvidenceService
from tests.evidence_contract import ATTRS, CLAIM, TEXT, EvidenceContract, cand
from tests.factories import NOW
from tests.memrepo import MemRepo


class MemEnv:
    def make_env(self):
        repo = MemRepo()
        env = {"A": ("wA", "rA"), "B": ("wB", "rB"), "D": ("wA", "rD")}
        for k, (w, r) in env.items():
            repo.register_research(r, w, is_demo=(k == "D"))
        return repo, env


class InMemoryEvidenceTests(MemEnv, EvidenceContract, unittest.TestCase):
    """Contract tests against the in-memory test double (validates service logic, not SQL)."""

    def test_source_race_returns_the_winner(self):
        class Racy(MemRepo):
            def add_source(self, s):
                if not getattr(self, "raced", False):
                    self.raced = True
                    import copy
                    other = copy.deepcopy(s)
                    other.id = "winner"
                    super().add_source(other)
                raise DuplicateError()
        repo = Racy()
        repo.register_research("rA", "wA")
        svc = EvidenceService(repo, clock=lambda: NOW)
        from app.evidence.domain import Scope
        s, created, via = svc.save_source(Scope("wA", "rA"), cand(), TEXT)
        self.assertEqual((s.id, created), ("winner", False))

    def test_claim_race_returns_the_winner(self):
        class Racy(MemRepo):
            def add_claim(self, c):
                import copy
                w = copy.deepcopy(c)
                w.id = "winner"
                super().add_claim(w)
                raise DuplicateError()
        repo = Racy()
        repo.register_research("rA", "wA")
        from app.evidence.domain import Scope
        c, created = EvidenceService(repo).create_claim(Scope("wA", "rA"), CLAIM, "market_size", ATTRS)
        self.assertEqual((c.id, created), ("winner", False))


if __name__ == "__main__":
    unittest.main()
