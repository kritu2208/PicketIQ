"""Database engine and session management.

Provides SQLAlchemy engine, session maker, declarative base, and dependency
for session lifecycle management.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import DATABASE_URL

# Engine with connection health checking enabled
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# Thread-local session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for declarative ORM models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session.
    
    Ensures the session is cleanly closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
