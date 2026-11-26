"""Database models — the 6 plan tables + one small problem_feedback table.

problems: identified by (contest_id, index) — Codeforces' own ids, so upserts
are reliable. submissions: cf_submission_id is unique (idempotency key).
revisions: spaced-repetition queue. notes: schema only, Phase 2.
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from .db import Base


def _now():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    cf_handle = Column(String, nullable=True)
    platform = Column(String, nullable=False, default="codeforces")
    current_rating = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)


class Problem(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True)
    contest_id = Column(Integer, nullable=False)
    index = Column(String, nullable=False)  # e.g. "A", "B1"
    name = Column(String, nullable=False)
    rating = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=False, default=list)  # JSON list, PG-compatible
    platform = Column(String, nullable=False, default="codeforces")

    __table_args__ = (UniqueConstraint("contest_id", "index", "platform"),)


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True)
    cf_submission_id = Column(Integer, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    verdict = Column(String, nullable=False)  # OK, WRONG_ANSWER, ...
    language = Column(String, nullable=True)
    submitted_at = Column(DateTime, nullable=False)
    time_consumed = Column(Integer, nullable=True)  # ms
    memory_consumed = Column(Integer, nullable=True)  # bytes
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        Index("ix_submissions_user_time", "user_id", "submitted_at"),
        Index("ix_submissions_user_verdict", "user_id", "verdict"),
    )


class Revision(Base):
    __tablename__ = "revisions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    interval_days = Column(Integer, nullable=False, default=1)
    interval_step = Column(Integer, nullable=False, default=0)  # index into [1,3,7,14,30]
    due_date = Column(DateTime, nullable=False)
    last_result = Column(String, nullable=True)  # again/hard/good/easy
    wrong_attempts = Column(Integer, nullable=False, default=0)
    done = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        Index("ix_revisions_user_due", "user_id", "due_date"),
        UniqueConstraint("user_id", "problem_id"),
    )


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="pending")  # pending/running/done/failed
    last_synced_submission_id = Column(Integer, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    total_synced = Column(Integer, nullable=False, default=0)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    body = Column(String, nullable=False, default="")
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "problem_id"),)


class ProblemFeedback(Base):
    """Later / Not interested on a recommendation. Small MVP addition so a
    dismissed problem never comes back."""

    __tablename__ = "problem_feedback"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    contest_id = Column(Integer, nullable=False)
    problem_index = Column(String, nullable=False)
    action = Column(String, nullable=False)  # later / not_interested
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "contest_id", "problem_index"),)
