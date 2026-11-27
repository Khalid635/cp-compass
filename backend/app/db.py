"""SQLAlchemy setup. SQLite locally, Postgres-compatible types only.

No Postgres-specific column types are used anywhere (tags are stored as a
JSON list, never ARRAY/JSONB), so the same models run on Neon Postgres.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

# Reel check #16 (2026-11-27): enforce TLS to Postgres in code, so a
# connection string without ?sslmode=require cannot silently downgrade.
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    connect_args = {"sslmode": "require"}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
