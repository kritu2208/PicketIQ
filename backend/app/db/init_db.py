"""Database table initialization script.

Creates all tables registered on SQLAlchemy Base.metadata.
Can be executed via CLI:
    python -m app.db.init_db [--drop]
"""

import argparse
import logging
import sys
from typing import Optional
from sqlalchemy import Engine

from app.db.session import engine as default_engine, Base
# Ensure all models are imported so their metadata is registered with Base
import app.db.models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("picket_iq.db.init")


def init_db(engine: Optional[Engine] = None, drop_existing: bool = False) -> None:
    """Create database tables from registered SQLAlchemy metadata.

    Args:
        engine: SQLAlchemy Engine instance. Defaults to application default_engine.
        drop_existing: If True, drops all existing tables before re-creating.
    """
    target_engine = engine or default_engine

    if drop_existing:
        logger.warning("Dropping all existing database tables...")
        Base.metadata.drop_all(bind=target_engine)
        logger.info("Existing database tables dropped.")

    logger.info("Creating database tables from SQLAlchemy metadata...")
    Base.metadata.create_all(bind=target_engine)

    table_names = list(Base.metadata.tables.keys())
    logger.info("Successfully initialized %d database tables: %s", len(table_names), ", ".join(table_names))


def main() -> None:
    """CLI entrypoint for database initialization."""
    parser = argparse.ArgumentParser(
        description="Initialize PicketIQ database tables."
    )
    parser.add_argument(
        "--drop",
        "--reset",
        action="store_true",
        dest="drop_existing",
        help="Drop all existing tables before re-creating.",
    )
    args = parser.parse_args()

    try:
        init_db(drop_existing=args.drop_existing)
    except Exception as exc:
        logger.error("Failed to initialize database tables: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
