"""
Database connection and session management

Usage:
    from database.db import get_db, init_db
"""

import os
import logging
from sqlalchemy import create_engine, text # type: ignore
from sqlalchemy.orm import sessionmaker, Session # type: ignore
from typing import Generator

from database.models import Base  # noqa: E402

logger = logging.getLogger(__name__)


DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set"
    )

if not DATABASE_URL.startswith("postgresql"):
    raise RuntimeError(
        f"Only PostgreSQL is supported. Got: {DATABASE_URL[:40]}"
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

logger.info(f"PostgreSQL engine created: {DATABASE_URL.split('@')[-1]}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    """
    Create all tables on startup.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified / created.")


def drop_all_tables() -> None:
    """Drop all tables."""
    Base.metadata.drop_all(bind=engine)
    logger.warning("All tables dropped.")




def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
