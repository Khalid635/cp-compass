""".ics calendar export tests (batch 5).

Covers: VCALENDAR shape (UID, DTSTART/DTEND, SUMMARY, URL) for
phase-BEFORE contests only, ICS text escaping, the attachment
headers, 401 without auth, and 502 when Codeforces fails.
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


from app.cf import CFError  # noqa: E402


@pytest.fixture()
def contests(monkeypatch):
    start = int(datetime(2026, 11, 28, 18, 0, tzinfo=timezone.utc).timestamp())

    async def _list():
        return [
            {"id": 1, "name": "Round #1, Div. 2", "phase": "BEFORE",
             "startTimeSeconds": start, "durationSeconds": 7200},
            {"id": 2, "name": "Round #2", "phase": "CODING",
             "startTimeSeconds": start - 3600, "durationSeconds": 7200},
            {"id": 3, "name": "Round #3", "phase": "FINISHED",
             "startTimeSeconds": start - 86400, "durationSeconds": 7200},
            {"id": 4, "name": "Round #4; Semi", "phase": "BEFORE",
             "startTimeSeconds": start + 86400, "durationSeconds": 3600},
        ]

    monkeypatch.setattr(mainmod.cf, "contest_list", _list)


def test_ics_export_shape(client, db, contests):
    u = _user(db)
    r = client.get("/api/v1/calendar/export.ics", headers=_auth_headers(u.id))
    assert r.status_code == 200
    assert "text/calendar" in r.headers["content-type"]
    assert "codeforces-contests.ics" in r.headers["content-disposition"]
    body = r.text
    assert "BEGIN:VCALENDAR" in body
    assert "END:VCALENDAR" in body
    assert body.count("BEGIN:VEVENT") == 2
    assert "UID:contest-1@rung" in body
    assert "UID:contest-4@rung" in body
    assert "UID:contest-2@rung" not in body
    assert "UID:contest-3@rung" not in body
    assert "DTSTART:20261128T180000Z" in body
    assert "DTEND:20261128T200000Z" in body
    assert "DTSTART:20261129T180000Z" in body
    assert "DTEND:20261129T190000Z" in body
    assert "SUMMARY:Round #1\\, Div. 2" in body
    assert "SUMMARY:Round #4\\; Semi" in body
    assert "URL:https://codeforces.com/contest/1" in body


def test_ics_export_requires_auth(client, contests):
    assert client.get("/api/v1/calendar/export.ics").status_code == 401


def test_ics_export_cf_failure_502(client, db, monkeypatch):
    async def _boom():
        raise CFError("Codeforces is down")

    monkeypatch.setattr(mainmod.cf, "contest_list", _boom)
    u = _user(db)
    r = client.get("/api/v1/calendar/export.ics", headers=_auth_headers(u.id))
    assert r.status_code == 502


def test_ics_export_no_upcoming_contests(client, db, monkeypatch):
    async def _empty():
        return [{"id": 9, "name": "Old Round", "phase": "FINISHED",
                 "startTimeSeconds": 1000000000, "durationSeconds": 7200}]

    monkeypatch.setattr(mainmod.cf, "contest_list", _empty)
    u = _user(db)
    r = client.get("/api/v1/calendar/export.ics", headers=_auth_headers(u.id))
    assert r.status_code == 200
    assert "BEGIN:VCALENDAR" in r.text
    assert "BEGIN:VEVENT" not in r.text
