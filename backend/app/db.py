"""SQLAlchemy setup. SQLite locally, Postgres-compatible types only.

No Postgres-specific column types are used anywhere (tags are stored as a
JSON list, never ARRAY/JSONB), so the same models run on Neon Postgres.
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

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


# ---------- Batch 7: Row-Level Security session context ------------------
# The app connects as ONE shared role (cpcompass_app), so Postgres cannot
# tell users apart by itself. Each session carries the authenticated
# user's id in the transaction-local setting app.current_user_id, and
# the RLS policies (migration 0010) compare the row's owner to it.
#
# The setting is transaction-local (set_config(..., true) == SET LOCAL):
# it dies with the transaction, so it can never leak across pooled
# connections to another request. The catch is that it ALSO dies at
# every db.commit() — and this codebase commits mid-request all over
# (token issuance, set_goal then settings_data, sync checkpoints).
# So set_rls_user() remembers the id in session.info, and the
# after_transaction_end hook below re-applies it after every commit
# AND rollback. Everything here is a no-op on SQLite (dev/test).
RLS_USER_SETTING = "app.current_user_id"


def _is_postgres(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def set_rls_user(db: Session, user_id: int) -> None:
    """Scope this session's RLS policies to user_id (Postgres only)."""
    db.info["rls_user_id"] = user_id
    if _is_postgres(db):
        db.execute(
            text("SELECT set_config(:key, :value, true)"),
            {"key": RLS_USER_SETTING, "value": str(user_id)},
        )


def clear_rls_user(db: Session) -> None:
    """Forget the session's RLS user. The setting is transaction-local,
    so it also dies at the next commit/rollback on its own."""
    db.info.pop("rls_user_id", None)
    if _is_postgres(db):
        db.execute(
            text("SELECT set_config(:key, '', true)"),
            {"key": RLS_USER_SETTING},
        )


@event.listens_for(Session, "after_transaction_end")
def _reapply_rls_user(session: Session, transaction) -> None:
    """Re-apply the remembered RLS user after a transaction ends
    (commit or rollback). SET LOCAL dies with the transaction, so
    without this the first commit in a request would silently un-scope
    every later query in that request. Nested (savepoint) ends do not
    clear SET LOCAL, so they are skipped. Executing here autobegins a
    new transaction carrying the setting; the pool reset rolls it back
    on session close, so nothing leaks."""
    if transaction.nested:
        return
    user_id = session.info.get("rls_user_id")
    if user_id is None:
        return
    if _is_postgres(session):
        session.execute(
            text("SELECT set_config(:key, :value, true)"),
            {"key": RLS_USER_SETTING, "value": str(user_id)},
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
