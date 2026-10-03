"""UNEXECUTED in the authoring environment (needs sqlalchemy). Runs the SAME contract as tests/test_evidence_service.py against
SqlEvidenceRepository on SQLite. SQLite does not enforce the composite FKs / Postgres triggers: those need a Postgres run."""
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.db import Base
from app.models import ResearchProject, User, Workspace
from app.repositories.evidence import SqlEvidenceRepository
from tests.evidence_contract import EvidenceContract


class SqlEvidenceTests(EvidenceContract, unittest.TestCase):
    def make_env(self):
        eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(eng)
        sf = sessionmaker(eng, expire_on_commit=False)
        with sf() as db:
            u, wa, wb = User(email="a@x.com", name="A", password_hash="x"), Workspace(name="A", slug="a"), Workspace(name="B", slug="b")
            db.add_all([u, wa, wb])
            db.flush()
            mk = lambda w, demo=False: ResearchProject(workspace_id=w.id, owner_id=u.id, title="T", objective="Analyze the market",
                                                       status="planning", is_demo=demo)
            ra, rb, rd = mk(wa), mk(wb), mk(wa, True)
            db.add_all([ra, rb, rd])
            db.commit()
            env = {"A": (str(wa.id), str(ra.id)), "B": (str(wb.id), str(rb.id)), "D": (str(wa.id), str(rd.id))}
        return SqlEvidenceRepository(sf), env
