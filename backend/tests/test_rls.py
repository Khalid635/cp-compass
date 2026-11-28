"""Batch 7 tests: RLS policies (migration 0010).

- test_migration_0010_roundtrip (SQLite, always runs): the migration
  is a Postgres no-op there, so upgrade/downgrade must not crash and
  must change nothing.
- Postgres-gated tests (skip unless TEST_POSTGRES_OWNER_URL and
  TEST_POSTGRES_APP_URL are set): alembic to head on a throwaway DB
  as owner, then prove the isolation as the app role (cpcompass_app).
  URLs come from the environment only -- never in code.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.config as config  # noqa: E402
import app.db as dbmod  # noqa: E402
from app import models  # noqa: E402
from app.db import Base, clear_rls_user, set_rls_user  # noqa: E402

OWNER_URL = os.environ.get("TEST_POSTGRES_OWNER_URL")
APP_URL = os.environ.get("TEST_POSTGRES_APP_URL")


def test_migration_0010_roundtrip(tmp_path, monkeypatch):
    """0010 on SQLite: no-op upgrade/downgrade, version moves 0009 ->
    0010 -> 0009 -> 0010 without crashing. Mirrors the 0008 test."""
    import sqlite3

    dbfile = tmp_path / "mig0010.db"
    url = "sqlite:///" + str(dbfile)
    monkeypatch.setattr(config, "DATABASE_URL", url)
    from alembic import command
    from alembic.config import Config

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)

    def _version():
        con = sqlite3.connect(str(dbfile))
        rows = con.execute("SELECT version_num FROM alembic_version").fetchall()
        con.close()
        return rows[0][0] if rows else None

    command.upgrade(cfg, "0009")
    assert _version() == "0009"
    command.upgrade(cfg, "0010")
    assert _version() == "0010"
    command.downgrade(cfg, "0009")
    assert _version() == "0009"
    command.upgrade(cfg, "0010")
    assert _version() == "0010"


# ---------------------------------------------------------------------------
# Postgres-gated isolation probes (throwaway DB, owner + app role).
# ---------------------------------------------------------------------------

TABLES = [t.name for t in Base.metadata.sorted_tables]


@pytest.fixture(scope="module")
def pg_schema():
    if not OWNER_URL or not APP_URL:
        pytest.skip("Postgres RLS tests need TEST_POSTGRES_OWNER_URL "
                    "and TEST_POSTGRES_APP_URL")
    from alembic import command
    from alembic.config import Config

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", OWNER_URL)
    command.upgrade(cfg, "head")
    yield


@pytest.fixture()
def pg_seed(pg_schema):
    """Two users + one row each in the user-owned tables (as owner,
    which bypasses RLS). Returns {a_id, b_id, ...row ids}."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    owner_engine = create_engine(OWNER_URL)
    OwnerSession = sessionmaker(bind=owner_engine)
    db = OwnerSession()
    try:
        # TRUNCATE via raw SQL (ORM has no truncate helper).
        from sqlalchemy import text as _text
        db.execute(_text("TRUNCATE TABLE " + ", ".join(
            f'"{t}"' for t in TABLES) + " RESTART IDENTITY CASCADE"))
        db.commit()
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        a = models.User(email="a@rls.test", password_hash="x",
                        email_verified=True)
        b = models.User(email="b@rls.test", password_hash="x",
                        email_verified=True)
        db.add_all([a, b])
        db.commit()
        prob = models.Problem(contest_id=1, index="A", name="P1",
                              rating=800, tags=["math"], platform="codeforces")
        db.add(prob)
        db.commit()
        sub_a = models.Submission(
            cf_submission_id=101, user_id=a.id, problem_id=prob.id,
            verdict="OK", submitted_at=now)
        sub_b = models.Submission(
            cf_submission_id=102, user_id=b.id, problem_id=prob.id,
            verdict="WRONG_ANSWER", submitted_at=now)
        db.add_all([sub_a, sub_b])
        note_b = models.ProblemNote(user_id=b.id, problem_id=prob.id,
                                    body="b secret note")
        rev_b = models.Revision(user_id=b.id, problem_id=prob.id,
                                interval_days=1, interval_step=0,
                                due_date=now + timedelta(days=1))
        hint_b = models.AiHint(user_id=b.id, problem_id=prob.id, step=1,
                               lang="en", text="b hint")
        db.add_all([note_b, rev_b, hint_b])
        db.add(models.RefreshToken(
            user_id=b.id, token_hash="b" * 64,
            expires_at=now + timedelta(days=7)))
        db.add(models.PasswordResetToken(
            user_id=b.id, token_hash="c" * 64,
            expires_at=now + timedelta(minutes=30)))
        db.add(models.SyncJob(user_id=b.id, status="done", total_synced=1))
        db.add(models.CfAccount(user_id=b.id, handle="Bee",
                                handle_norm="bee"))
        db.add(models.EmailVerification(
            user_id=b.id, email=b.email, code_hash="d" * 64,
            expires_at=now + timedelta(minutes=15)))
        db.add(models.TotpSecret(user_id=b.id, secret_encrypted="enc"))
        db.add(models.BackupCode(user_id=b.id, code_hash="e" * 64))
        db.add(models.HandleVerification(
            user_id=b.id, handle="Bee", handle_norm="bee",
            token_hash="f" * 64, expires_at=now + timedelta(minutes=60)))
        db.commit()
        yield {"a": a.id, "b": b.id, "prob": prob.id,
               "sub_a": sub_a.id, "sub_b": sub_b.id,
               "note_b": note_b.id, "rev_b": rev_b.id}
    finally:
        db.close()
        owner_engine.dispose()


def _app_engine():
    from sqlalchemy import create_engine

    return create_engine(APP_URL)


def _app_conn(engine):
    from sqlalchemy import text

    conn = engine.connect()
    return conn


def _setvar(conn, user_id):
    from sqlalchemy import text

    conn.execute(text("SELECT set_config('app.current_user_id', :v, true)"),
                 {"v": str(user_id)})


def _count(conn, table, where=""):
    from sqlalchemy import text

    q = f'SELECT count(*) FROM "{table}"'
    if where:
        q += f" WHERE {where}"
    return conn.execute(text(q)).scalar()


def test_rls_strict_isolation(pg_seed):
    """As A: only A's rows are visible; B's rows cannot be read,
    updated or deleted; INSERT for B is rejected."""
    ids = pg_seed
    engine = _app_engine()
    try:
        conn = _app_conn(engine)
        try:
            _setvar(conn, ids["a"])
            assert _count(conn, "submissions") == 1
            assert _count(conn, "submissions",
                          f"id = {ids['sub_b']}") == 0
            assert _count(conn, "problem_notes") == 0
            assert _count(conn, "revisions") == 0
            assert _count(conn, "ai_hints") == 0
            # UPDATE of B's row touches 0 rows (no error, no effect).
            from sqlalchemy import text
            r = conn.execute(
                text("UPDATE submissions SET verdict = 'OK' "
                     f"WHERE id = {ids['sub_b']}"))
            assert r.rowcount == 0
            r = conn.execute(
                text("DELETE FROM problem_notes "
                     f"WHERE id = {ids['note_b']}"))
            assert r.rowcount == 0
            # INSERT for A works; INSERT for B violates the policy.
            # (created_at has only a Python-side default, so raw SQL
            # must supply it.)
            conn.execute(
                text("INSERT INTO submissions (cf_submission_id, user_id, "
                     "problem_id, verdict, submitted_at, created_at) "
                     "VALUES (201, :u, :p, 'OK', now(), now())"),
                {"u": ids["a"], "p": ids["prob"]})
            assert _count(conn, "submissions") == 2
            with pytest.raises(Exception, match="row-level security"):
                conn.execute(
                    text("INSERT INTO submissions (cf_submission_id, "
                         "user_id, problem_id, verdict, submitted_at, "
                         "created_at) VALUES (202, :u, :p, 'OK', now(), "
                         "now())"),
                    {"u": ids["b"], "p": ids["prob"]})
            conn.rollback()
        finally:
            conn.close()
    finally:
        engine.dispose()


def test_rls_no_context_exceptions(pg_seed):
    """With NO variable: strict tables return 0 rows, while the
    documented exceptions (users, problems, token tables, cf_accounts,
    sync_jobs) stay readable."""
    ids = pg_seed
    engine = _app_engine()
    try:
        conn = _app_conn(engine)
        try:
            assert _count(conn, "submissions") == 0
            assert _count(conn, "problem_notes") == 0
            assert _count(conn, "revisions") == 0
            assert _count(conn, "ai_hints") == 0
            assert _count(conn, "totp_secrets") == 0
            assert _count(conn, "backup_codes") == 0
            assert _count(conn, "handle_verifications") == 0
            assert _count(conn, "email_verifications") == 0
            # Documented exceptions: readable with no context.
            assert _count(conn, "users") == 2
            assert _count(conn, "problems") == 1
            assert _count(conn, "password_reset_tokens") == 1
            assert _count(conn, "refresh_tokens") == 1
            assert _count(conn, "cf_accounts") == 1
            assert _count(conn, "sync_jobs") == 1
            # ... but scoped once a context IS set.
            _setvar(conn, ids["a"])
            assert _count(conn, "users") == 1
            assert _count(conn, "sync_jobs") == 0
            conn.rollback()
        finally:
            conn.close()
    finally:
        engine.dispose()


def test_rls_context_survives_commit(pg_seed):
    """The app.db hook: set -> commit -> query is still scoped (this
    is what keeps set_goal, token issuance and sync checkpoints
    working after their mid-request commits)."""
    ids = pg_seed
    from sqlalchemy.orm import sessionmaker

    engine = _app_engine()
    try:
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            set_rls_user(db, ids["a"])
            assert db.query(models.Submission).count() == 1
            db.commit()
            assert db.query(models.Submission).count() == 1
            assert db.query(models.ProblemNote).count() == 0
            set_rls_user(db, ids["b"])
            assert db.query(models.Submission).count() == 1
            assert db.query(models.ProblemNote).count() == 1
            db.commit()
            assert db.query(models.ProblemNote).count() == 1
            clear_rls_user(db)
            db.commit()
            assert db.query(models.Submission).count() == 0
        finally:
            db.close()
    finally:
        engine.dispose()


def test_rls_public_profile_path(pg_seed):
    """The public-profile path: scoping to the TARGET user (after the
    opt-in check) sees that user's aggregates; scoping to the
    requester does not."""
    ids = pg_seed
    engine = _app_engine()
    try:
        conn = _app_conn(engine)
        try:
            _setvar(conn, ids["a"])
            assert _count(conn, "submissions",
                          f"user_id = {ids['b']}") == 0
            _setvar(conn, ids["b"])
            assert _count(conn, "submissions",
                          f"user_id = {ids['b']}") == 1
            conn.rollback()
        finally:
            conn.close()
    finally:
        engine.dispose()


def test_rls_problems_writes_need_context(pg_seed):
    """The shared catalog: readable by everyone, writable only with a
    user context."""
    ids = pg_seed
    from sqlalchemy import text

    engine = _app_engine()
    try:
        conn = _app_conn(engine)
        try:
            assert _count(conn, "problems") == 1
            with pytest.raises(Exception, match="row-level security"):
                conn.execute(text(
                    "INSERT INTO problems (contest_id, index, name, "
                    "rating, tags, platform) VALUES "
                    "(2, 'A', 'P2', 800, '[]', 'codeforces')"))
            conn.rollback()
            _setvar(conn, ids["a"])
            conn.execute(text(
                "INSERT INTO problems (contest_id, index, name, "
                "rating, tags, platform) VALUES "
                "(2, 'A', 'P2', 800, '[]', 'codeforces')"))
            assert _count(conn, "problems") == 2
            conn.rollback()
        finally:
            conn.close()
    finally:
        engine.dispose()


def test_rls_alembic_version_readonly(pg_seed):
    """alembic_version: the app role can read it, never write it."""
    from sqlalchemy import text

    engine = _app_engine()
    try:
        conn = _app_conn(engine)
        try:
            v = conn.execute(
                text("SELECT version_num FROM alembic_version")).scalar()
            assert v == "0010"
            with pytest.raises(Exception, match="row-level security"):
                conn.execute(text(
                    "INSERT INTO alembic_version (version_num) "
                    "VALUES ('9999')"))
            conn.rollback()
        finally:
            conn.close()
    finally:
        engine.dispose()
