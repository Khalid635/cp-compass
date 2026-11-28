"""Public profile tests (batch 5).

Covers: opt-in default OFF, the toggle endpoint (auth + flip),
GET /api/v1/u/{handle} 404 for private/unknown handles, the payload
shape when public (and that no email/user id ever leaks), and the
migration 0008 round-trip on SQLite.
Runs against a throwaway SQLite DB (TEST_DATABASE_URL). No network.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import secrets

import pytest
from fastapi.testclient import TestClient

os.environ["TEST_DATABASE_URL"] = "sqlite:///./test_cpcompass.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.config as config  # noqa: E402
config.DATABASE_URL = "sqlite:///./test_cpcompass.db"

import app.db as dbmod  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

dbmod.engine = create_engine(
    config.DATABASE_URL, connect_args={"check_same_thread": False})
dbmod.SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=dbmod.engine)

from app import auth, models, ratelimit  # noqa: E402
from app.db import Base  # noqa: E402
import app.main as mainmod  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    if os.path.exists("test_cpcompass.db"):
        os.remove("test_cpcompass.db")
    Base.metadata.create_all(bind=dbmod.engine)
    ratelimit.reset()
    yield
    dbmod.engine.dispose()
    if os.path.exists("test_cpcompass.db"):
        os.remove("test_cpcompass.db")


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def db():
    session = dbmod.SessionLocal()
    yield session
    session.close()


def _user(db, email="a@test.dev", verified=True):
    u = models.User(email=email,
                    password_hash=auth.hash_password("secret123"),
                    email_verified=verified, current_rating=1400)
    db.add(u)
    db.commit()
    return u


def _handle(db, user_id, handle="Khalid_Bin_Masud"):
    a = models.CfAccount(user_id=user_id, handle=handle,
                         handle_norm=handle.lower())
    db.add(a)
    db.commit()
    return a


def _tokens(user_id):
    session = dbmod.SessionLocal()
    try:
        return auth.issue_tokens(session, user_id)
    finally:
        session.close()


ORIGIN = "http://localhost:5173"


def _csrf_token():
    return secrets.token_urlsafe(32)


def _anon_headers():
    """CSRF headers for an unauthenticated mutation (register/login/
    verify/forgot/reset/callback): a fresh CSRF token in both the
    Cookie header and the X-CSRF-Token header, plus Origin. The server
    only compares header to cookie — no stored token — so a minted
    token is valid, and nothing touches the client's cookie jar."""
    csrf = _csrf_token()
    return {"Cookie": f"cp_csrf={csrf}", "X-CSRF-Token": csrf, "Origin": ORIGIN}

def _auth_headers(user_id):
    """Cookie-based auth (Batch 6, N4): tokens travel as
    HttpOnly-cookie values in an explicit Cookie header, plus
    the double-submit CSRF header and Origin. Same signature
    as before, so call sites don't change — and per-request
    cookies keep two-user tests working."""
    tokens = _tokens(user_id)
    csrf = _csrf_token()
    cookie = (f"cp_access={tokens['access_token']}; "
              f"cp_refresh={tokens['refresh_token']}; cp_csrf={csrf}")
    return {"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": ORIGIN}


def _access_token(user_id):
    return _tokens(user_id)["access_token"]


def _problem(db, contest_id=231, index="A", name="Team", rating=800,
             tags=None):
    p = models.Problem(contest_id=contest_id, index=index, name=name,
                       rating=rating, tags=tags or ["implementation"])
    db.add(p)
    db.commit()
    return p


_sid = [2000]


def _submission(db, user_id, problem_id, verdict="OK", when=None):
    _sid[0] += 1
    s = models.Submission(cf_submission_id=_sid[0],
                          user_id=user_id, problem_id=problem_id,
                          verdict=verdict, language="C++17",
                          submitted_at=when or datetime.utcnow())
    db.add(s)
    db.commit()
    return s


def test_public_profile_default_off(client, db):
    u = _user(db)
    _handle(db, u.id)
    r = client.get("/api/v1/settings", headers=_auth_headers(u.id))
    assert r.status_code == 200
    assert r.json()["public_profile"] is False
    r = client.get("/api/v1/u/Khalid_Bin_Masud")
    assert r.status_code == 404


def test_public_profile_toggle_requires_auth(client, db):
    u = _user(db)
    r = client.post("/api/v1/settings/public-profile", json={"public": True},
                    headers=_anon_headers())
    assert r.status_code == 401


def test_public_profile_toggle_flips(client, db):
    u = _user(db)
    r = client.post("/api/v1/settings/public-profile", json={"public": True},
                    headers=_auth_headers(u.id))
    assert r.status_code == 200
    assert r.json() == {"public_profile": True}
    r = client.get("/api/v1/settings", headers=_auth_headers(u.id))
    assert r.json()["public_profile"] is True
    r = client.post("/api/v1/settings/public-profile", json={"public": False},
                    headers=_auth_headers(u.id))
    assert r.json() == {"public_profile": False}


def test_public_profile_404_unknown_handle(client):
    assert client.get("/api/v1/u/NoSuchHandle").status_code == 404


def test_public_profile_payload_when_public(client, db):
    u = _user(db)
    _handle(db, u.id)
    p1 = _problem(db, 231, "A", "Team", 800, ["implementation", "math"])
    p2 = _problem(db, 231, "B", "Queue", 1000, ["dp"])
    _submission(db, u.id, p1.id, verdict="OK",
                when=datetime.utcnow() - timedelta(days=1))
    _submission(db, u.id, p1.id, verdict="WRONG_ANSWER")
    _submission(db, u.id, p2.id, verdict="OK")
    job = models.SyncJob(user_id=u.id, status="done", total_synced=3,
                         last_synced_at=datetime.utcnow())
    db.add(job)
    db.commit()
    client.post("/api/v1/settings/public-profile", json={"public": True},
                headers=_auth_headers(u.id))
    r = client.get("/api/v1/u/khalid_bin_masud")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"handle", "rank", "current_rating", "solved",
                                "attempted", "current_streak", "top_tags",
                                "last_synced_at"}
    assert body["handle"] == "Khalid_Bin_Masud"
    assert body["current_rating"] == 1400
    assert body["solved"] == 2
    assert body["attempted"] == 3
    assert body["current_streak"] >= 1
    assert body["last_synced_at"] is not None
    assert isinstance(body["top_tags"], list)
    assert body["top_tags"][0]["tag"] in ("implementation", "math", "dp")
    assert "email" not in r.text and "user_id" not in r.text


def test_public_profile_never_leaks_when_private(client, db):
    u = _user(db, email="secret@test.dev")
    _handle(db, u.id)
    p = _problem(db)
    _submission(db, u.id, p.id, verdict="OK")
    r = client.get("/api/v1/u/Khalid_Bin_Masud")
    assert r.status_code == 404
    assert "secret@test.dev" not in r.text


def test_migration_0008_roundtrip(tmp_path, monkeypatch):
    import sqlite3
    dbfile = tmp_path / "mig0008.db"
    url = "sqlite:///" + str(dbfile)
    monkeypatch.setattr(config, "DATABASE_URL", url)
    from alembic import command
    from alembic.config import Config
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)

    def _has_col():
        con = sqlite3.connect(str(dbfile))
        cols = [row[1] for row in con.execute("PRAGMA table_info(users)")]
        con.close()
        return "public_profile" in cols

    command.upgrade(cfg, "0007")
    assert not _has_col()
    command.upgrade(cfg, "0008")
    assert _has_col()
    command.downgrade(cfg, "0007")
    assert not _has_col()
    command.upgrade(cfg, "0008")
    assert _has_col()
