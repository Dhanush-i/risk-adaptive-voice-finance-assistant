"""
Database Setup — SQLAlchemy + SQLite
=====================================
Async-compatible SQLAlchemy engine and session factory.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator

# Base class for all ORM models
Base = declarative_base()


def get_engine(database_url: str = "sqlite:///storage/voice_finance.db"):
    """Create SQLAlchemy engine."""
    # SQLite needs check_same_thread=False for FastAPI
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        echo=False,
    )
    return engine


def get_session_factory(engine) -> sessionmaker:
    """Create session factory."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Default engine and session (initialized on import)
_engine = None
_SessionLocal = None


def init_db(database_url: str = "sqlite:///storage/voice_finance.db"):
    """Initialize the database engine and session factory."""
    global _engine, _SessionLocal
    _engine = get_engine(database_url)
    _SessionLocal = get_session_factory(_engine)
    return _engine, _SessionLocal


def create_tables(engine=None):
    """Create all tables defined by ORM models."""
    if engine is None:
        engine = _engine
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    # Import models to register them with Base
    from backend.app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    print("[DB] All tables created successfully.")


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency — yields a database session.
    Usage: db: Session = Depends(get_db)
    """
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
