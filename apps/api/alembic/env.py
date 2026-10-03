from alembic import context
from sqlalchemy import create_engine
from app.core.config import settings
from app.core.db import Base
import app.models  # noqa: F401

eng = create_engine(settings.database_url)
with eng.connect() as conn:
    context.configure(connection=conn, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
