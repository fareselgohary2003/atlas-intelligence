"""DEMO_MODE seed: demo projects in Planning status with NO invented counts or progress. Every row is flagged is_demo=True (UI: MOCK).
Sources/claims appear only when the demo research is actually run."""
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import ResearchProject, User, Workspace, WorkspaceMember
from app.core.security import hash_password

DEMO = [
    ("Saudi B2B SaaS Market Opportunity", "Analyze the opportunity for launching a B2B SaaS product in Saudi Arabia, targeting medium-sized businesses."),
    ("European Fintech Analysis", "Map the competitive landscape for retail fintech in the EU."),
    ("Cloud Security Landscape", "Compare cloud security vendors and pricing for mid-market buyers."),
    ("GCC Logistics Automation", "Assess demand for logistics automation software across the GCC."),
]


def main():
    if not settings.demo_mode:
        return
    with SessionLocal() as db:
        user_email = "fareselgohary2003@gmail.com"
        existing_user = db.scalar(select(User).where(User.email == user_email))
        if not existing_user:
            u = User(email=user_email, name="Fares Elgohary", password_hash=hash_password("fares1234"))
            ws = Workspace(name="Atlas Workspace (Pro)", slug="atlas-workspace-pro")
            db.add_all([u, ws])
            db.flush()
            db.add(WorkspaceMember(workspace_id=ws.id, user_id=u.id, role="owner"))
            for t, o in DEMO:
                db.add(ResearchProject(workspace_id=ws.id, owner_id=u.id, title=t, objective=o, status="planning", is_demo=True, depth="deep",
                                       geography="Saudi Arabia" if "Saudi" in t else None))
            db.commit()
            print(f"Seeded user data: {user_email} / fares1234")

        # Also seed demo@atlas.dev as fallback
        if not db.scalar(select(User).where(User.email == "demo@atlas.dev")):
            u2 = User(email="demo@atlas.dev", name="Demo User", password_hash=hash_password("demo1234"))
            ws2 = Workspace(name="Production (demo)", slug="production-demo")
            db.add_all([u2, ws2])
            db.flush()
            db.add(WorkspaceMember(workspace_id=ws2.id, user_id=u2.id, role="owner"))
            for t, o in DEMO:
                db.add(ResearchProject(workspace_id=ws2.id, owner_id=u2.id, title=t, objective=o, status="planning", is_demo=True, depth="deep",
                                       geography="Saudi Arabia" if "Saudi" in t else None))
            db.commit()


if __name__ == "__main__":
    main()
