"""SSE sync-progress stream tests (batch 5).

Covers: 401 with no/bad token (incl. a refresh token), the never-state
for a user with no job, state + terminal done/failed events, live
progress events as total_synced changes, and that a token can never read another user's job.SSE sync-progress stream tests (batch 5).

Covers: 401 with no/bad token (incl. a refresh token), the never-state
for a user with no job, state + terminal done/failed events, live
progress events as total_synced changes, and that a token can only
ever read its own user's job.
Runs against a throwaway SQLite DB (TEST_DATABASE_URL). No network.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

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


def _auth_headers(user_id):
    tokens = _tokens(user_id)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _access_token(user_id):
    return _tokens(user_id)["access_token"]


def _job(db, user_id, status="pending", total=0, error=None):
    j = models.SyncJob(user_id=user_id, status=status,
                       total_synced=total, error=error)
    db.add(j)
    db.commit()
    return j


def test_stream_401_no_token(client):
    assert client.get("/api/v1/sync/stream").status_code == 401


def test_stream_401_bad_token(client):
    assert client.get("/api/v1/sync/stream?token=nope").status_code == 401


def test_stream_401_refresh_token_is_not_an_access_token(client, db):
    u = _user(db)
    refresh = _tokens(u.id)["refresh_token"]
    r = client.get(f"/api/v1/sync/stream?token={refresh}")
    assert r.status_code == 401


def test_stream_never_state_no_job(client, db):
    u = _user(db)
    r = client.get(f"/api/v1/sync/stream?token={_access_token(u.id)}")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "event: state" in r.text
    assert '"status": "never"' in r.text


def test_stream_done_job_closes(client, db):
    u = _user(db)
    _job(db, u.id, status="done", total=12)
    r = client.get(f"/api/v1/sync/stream?token={_access_token(u.id)}")
    assert r.status_code == 200
    assert "event: state" in r.text
    assert "event: done" in r.text
    assert '"total_synced": 12' in r.text


def test_stream_failed_job_closes(client, db):
    u = _user(db)
    _job(db, u.id, status="failed", total=3, error="Codeforces is down")
    r = client.get(f"/api/v1/sync/stream?token={_access_token(u.id)}")
    assert r.status_code == 200
    assert "event: failed" in r.text
    assert "Codeforces is down" in r.text


def test_stream_only_own_job(client, db):
    a = _user(db, email="a@test.dev")
    b = _user(db, email="b@test.dev")
    _job(db, b.id, status="running", total=42)
    r = client.get(f"/api/v1/sync/stream?token={_access_token(a.id)}")
    assert r.status_code == 200
    assert '"status": "never"' in r.text
    assert "42" not in r.text


def test_stream_live_progress(client, db, monkeypatch):
    import threading
    import time
    monkeypatch.setattr(mainmod, "SSE_POLL_S", 0.05)
    u = _user(db)
    job = _job(db, u.id, status="running", total=0)
    results = {}

    def _get():
        results["r"] = client.get(
            f"/api/v1/sync/stream?token={_access_token(u.id)}")

    t = threading.Thread(target=_get, daemon=True)
    t.start()
    time.sleep(0.3)
    s = dbmod.SessionLocal()
    j = s.query(models.SyncJob).get(job.id)
    j.total_synced = 5
    s.commit()
    time.sleep(0.3)
    j = s.query(models.SyncJob).get(job.id)
    j.status = "done"
    j.total_synced = 7
    s.commit()
    s.close()
    t.join(timeout=15)
    assert not t.is_alive()
    body = results["r"].text
    assert "event: state" in body
    assert "event: progress" in body
    assert '"total_synced": 5' in body
    assert "event: done" in body
    assert '"total_synced": 7' in body
