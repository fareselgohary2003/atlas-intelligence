import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core import security
from app.core.db import Base, get_db
from app.main import app


@pytest.fixture
def client():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    S = sessionmaker(eng, expire_on_commit=False)

    def override():
        with S() as s:
            yield s

    from app.api.evidence import evidence_repo
    from app.repositories.evidence import SqlEvidenceRepository
    app.dependency_overrides[get_db] = override
    from app.api.reports import report_service
    from app.reporting.service import ReportService
    from app.repositories.reports import SqlReportInputs, SqlReportRepository
    app.dependency_overrides[evidence_repo] = lambda: SqlEvidenceRepository(S)
    app.dependency_overrides[report_service] = lambda: ReportService(SqlReportInputs(S, SqlEvidenceRepository(S)), SqlReportRepository(S))
    security.reset_limits()
    c = TestClient(app)
    c.sf = S
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sf():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return sessionmaker(eng, expire_on_commit=False)
