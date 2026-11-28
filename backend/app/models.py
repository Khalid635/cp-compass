"""Database models — the blueprint's 11 tables + refresh-token storage.

Blueprint schema (11 tables):
  users, cf_accounts, problems, submissions, rating_history, sync_jobs,
  revisions, problem_notes, problem_preferences, daily_stats, weekly_reports.
Plus refresh_tokens (JWT refresh + revocation, blueprint §11).

Rules enforced here:
- users.email unique; cf_accounts.handle case-insensitive unique
  (stored as handle_norm, lowercased).
- problems is a GLOBAL catalog: one row per problem, shared across users;
  (contest_id, index, platform) unique.
- submissions.cf_submission_id unique (idempotency key for sync).
- revisions: one record per (user, problem).
- problem_preferences: one state per (user, problem).
- Every user-owned row is reached through user_id so ownership checks are
  one filter away. Foreign keys use ON DELETE CASCADE where the child row
  is meaningless without the parent.
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
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
    # Google OAuth (batch google-oauth): NULL for Google-only accounts,
    # which have no password. Password login for them is a plain 401.
    password_hash = Column(String, nullable=True)
    # Google `sub` claim, set when the account signs in with Google or
    # links a Google account. Unique so one Google account links to at
    # most one CP Compass account.
    google_id = Column(String, nullable=True, unique=True, index=True)
    platform = Column(String, nullable=False, default="codeforces")
    current_rating = Column(Integer, nullable=True)
    # Weekly practice goal: problems to solve per week (Phase 2, Settings).
    weekly_goal = Column(Integer, nullable=False, default=5)
    # Batch 1 security: email verified via a code at signup; TOTP 2FA is
    # optional per user. Accounts created before verification existed are
    # backfilled verified by migration 0003 (dev DB only).
    email_verified = Column(Boolean, nullable=False, default=False)
    totp_enabled = Column(Boolean, nullable=False, default=False)
    # Last ML retrain (Batch 1 F5 cooldown: max 1 retrain per user per hour).
    last_retrain_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)


class CfAccount(Base):
    """One connected Codeforces handle per user (MVP: single platform)."""

    __tablename__ = "cf_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, unique=True, index=True)
    handle = Column(String, nullable=False)
    handle_norm = Column(String, nullable=False, unique=True)  # lowercased
    rank = Column(String, nullable=True)
    connected_at = Column(DateTime, default=_now, nullable=False)


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
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"),
                        nullable=False)
    verdict = Column(String, nullable=False)  # OK, WRONG_ANSWER, ...
    language = Column(String, nullable=True)
    submitted_at = Column(DateTime, nullable=False)
    time_consumed = Column(Integer, nullable=True)  # ms
    memory_consumed = Column(Integer, nullable=True)  # bytes
    # Batch 2: tests passed before the verdict (Codeforces user.status
    # returns it). NULL until backfilled — old rows predate the column.
    passed_test_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        # Query-driven: recent list (user, time), verdict filters (user,
        # verdict), heatmap/streak (user, verdict, time).
        Index("ix_submissions_user_time", "user_id", "submitted_at"),
        Index("ix_submissions_user_verdict", "user_id", "verdict"),
        Index("ix_submissions_user_verdict_time", "user_id", "verdict",
              "submitted_at"),
    )


class AiHint(Base):
    """One cached AI hint (Hint Ladder, batch ai-hint-ladder).

    One row per (user, problem, step) — the cache key. `lang` records
    the language the text was generated in; switching UI language
    regenerates the step (counts against the daily limit).
    """

    __tablename__ = "ai_hints"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"),
                        nullable=False)
    step = Column(Integer, nullable=False)  # 1 nudge, 2 approach, 3 insight
    lang = Column(String, nullable=False, default="en")
    text = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        Index("ix_ai_hints_user_created", "user_id", "created_at"),
        UniqueConstraint("user_id", "problem_id", "step"),
    )


class HintUsage(Base):
    """One row per AI hint GENERATION (Hint Ladder, batch ai-hint-ladder).

    The daily limit counts generations, not cached rows: a language
    regeneration updates the AiHint row in place, so counting AiHint
    rows would under-count. Cache hits insert nothing here.
    """

    __tablename__ = "hint_usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        Index("ix_hint_usage_user_created", "user_id", "created_at"),
    )


# ---------------------------------------------------------------------------
# Batch 4 — contest post-mortem AI.
# ---------------------------------------------------------------------------


class PostmortemAnalysis(Base):
    """One cached AI analysis of a contest post-mortem (batch 4).

    One row per (user, contest) — the cache key. `lang` records the
    language the text was generated in; switching UI language
    regenerates the row in place (counts against the daily limit,
    like hints).
    """

    __tablename__ = "postmortem_analysis"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    contest_id = Column(Integer, nullable=False)
    lang = Column(String, nullable=False, default="en")
    text = Column(String, nullable=False)
    model = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (
        Index("ix_postmortem_analysis_user_created", "user_id", "created_at"),
        UniqueConstraint("user_id", "contest_id"),
    )


class PostmortemUsage(Base):
    """One row per post-mortem analysis GENERATION (batch 4).

    The daily limit counts generations, not cached rows: a language
    regeneration updates the PostmortemAnalysis row in place, so
    counting PostmortemAnalysis rows would under-count. Cache hits
    insert nothing here.
    """

    __tablename__ = "postmortem_usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    contest_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        Index("ix_postmortem_usage_user_created", "user_id", "created_at"),
    )


class RatingHistory(Base):
    """One row per rated contest, newest last. Built from user.rating."""

    __tablename__ = "rating_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    contest_id = Column(Integer, nullable=False)
    contest_name = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)  # newRating
    # Rating before the contest (from user.rating's oldRating). NULL on
    # rows synced before Phase 2 — the delta is then chained from the
    # previous contest's rating instead.
    old_rating = Column(Integer, nullable=True)
    rated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "contest_id"),)


class Revision(Base):
    __tablename__ = "revisions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"),
                        nullable=False)
    interval_days = Column(Integer, nullable=False, default=1)
    interval_step = Column(Integer, nullable=False, default=0)  # index into [1,3,7,14,30]
    due_date = Column(DateTime, nullable=False)
    last_result = Column(String, nullable=True)  # again/hard/good/easy
    wrong_attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (
        Index("ix_revisions_user_due", "user_id", "due_date"),
        UniqueConstraint("user_id", "problem_id"),
    )


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    # pending / running / done / failed
    status = Column(String, nullable=False, default="pending")
    last_synced_submission_id = Column(Integer, nullable=True)
    # Pagination checkpoint: the `from` value of the next page to fetch.
    checkpoint_from = Column(Integer, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    total_synced = Column(Integer, nullable=False, default=0)
    attempts = Column(Integer, nullable=False, default=0)
    # DB-backed lease: who owns this run and until when. A running job
    # whose lease expired is stale and may be reclaimed.
    lease_owner = Column(String, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)


class ProblemNote(Base):
    """Personal notes on a problem (blueprint §9, High). Schema only here;
    the notes UI rides with the Problem Detail page (Phase 2)."""

    __tablename__ = "problem_notes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"),
                        nullable=False)
    body = Column(String, nullable=False, default="")
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "problem_id"),)


class ProblemPreference(Base):
    """later / dismissed / interested on a recommendation. 'later' and
    'dismissed' problems are excluded from future recommendations."""

    __tablename__ = "problem_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"),
                        nullable=False)
    state = Column(String, nullable=False)  # later | dismissed | interested
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "problem_id"),)


class DailyStat(Base):
    """Daily activity summary, rebuilt after every sync (feeds Calendar)."""

    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    day = Column(Date, nullable=False)
    solved = Column(Integer, nullable=False, default=0)  # accepted submissions
    attempted = Column(Integer, nullable=False, default=0)  # all submissions

    __table_args__ = (UniqueConstraint("user_id", "day"),)


class WeeklyReport(Base):
    """Weekly performance snapshot (feeds the Weekly Report page)."""

    __tablename__ = "weekly_reports"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    week_start = Column(Date, nullable=False)  # Monday
    solved = Column(Integer, nullable=False, default=0)
    attempted = Column(Integer, nullable=False, default=0)
    # JSON: per-tag acceptance that week, e.g. {"dp": 0.4, ...}
    tag_acceptance = Column(JSON, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("user_id", "week_start"),)


class RefreshToken(Base):
    """Hashed refresh tokens (SHA-256 of the raw token). Revocation is a
    row flag — logout revokes the token, logout-all revokes the user's set."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)


# ---------------------------------------------------------------------------
# Batch 1 security tables (audit F1 / F6).
# ---------------------------------------------------------------------------

class EmailVerification(Base):
    """One-time 6-digit signup code. Only the SHA-256 hash is stored; a
    code expires after EMAIL_CODE_EXPIRE_MINUTES and dies after
    EMAIL_CODE_MAX_ATTEMPTS wrong guesses. Old rows are deleted when a
    new code is issued so exactly one live code exists per user."""

    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    email = Column(String, nullable=False)
    code_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)


class TotpSecret(Base):
    """Per-user TOTP secret for authenticator-app 2FA. The secret is
    stored encrypted with a key derived from SECRET_KEY (see app.totp),
    never in plaintext. A row exists only while 2FA is being set up or
    is enabled; disabling 2FA deletes it."""

    __tablename__ = "totp_secrets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, unique=True, index=True)
    secret_encrypted = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)


class BackupCode(Base):
    """Single-use 2FA backup codes (SHA-256 hashed). Shown to the user
    once when 2FA is enabled or regenerated; a used code is marked and
    can never be reused."""

    __tablename__ = "backup_codes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    code_hash = Column(String, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)


class HandleVerification(Base):
    """Pending Codeforces handle ownership proof (audit F1). The user
    puts a random token in an editable Codeforces profile field
    (first name / last name / city / organization — user.info has no
    'about' field) and the backend confirms it via the public CF API
    before linking. Expires after 1 hour; 5 confirm attempts max."""

    __tablename__ = "handle_verifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    handle = Column(String, nullable=False)
    handle_norm = Column(String, nullable=False)
    token_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_now, nullable=False)

