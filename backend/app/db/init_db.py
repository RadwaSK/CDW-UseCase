"""Create the pgvector extension and all tables. Safe to run repeatedly.

MVP-scale schema management: the ORM models are the single source of truth,
applied with create_all rather than versioned migrations. If this project ever
needs to preserve data across a schema change, that's the point to introduce
Alembic.

Run: python -m app.db.init_db
"""

import logging

from sqlalchemy import text

from app.db.models import Base
from app.db.session import engine

logger = logging.getLogger(__name__)


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    logger.info("database_initialized", extra={"tables": len(Base.metadata.tables)})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print(f"initialized {len(Base.metadata.tables)} tables")
