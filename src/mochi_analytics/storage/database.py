"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mochi_analytics.db")

# SQLite for local development, PostgreSQL for production
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True  # Verify connections before using
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for database session.

    Usage:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """
    Get a database session for non-FastAPI code.

    Caller is responsible for closing the session.

    Usage:
        session = get_session()
        try:
            # Use session
            session.commit()
        finally:
            session.close()
    """
    return SessionLocal()


def create_tables():
    """Create all tables defined in models."""
    from mochi_analytics.storage.models import Base
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables (use with caution!)."""
    from mochi_analytics.storage.models import Base
    Base.metadata.drop_all(bind=engine)
