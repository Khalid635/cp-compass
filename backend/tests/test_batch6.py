"""Batch 6 tests: N1 register rate limit, N2 password recovery, N3
X-Forwarded-For, N4 HttpOnly cookies + CSRF, reel #8 audit logging,
section 8 rate limits on the four Batch 5 endpoints, the "Synced
never" wart, and the mailer outbox shape (incl. the N2 reset mail).

Runs against a throwaway SQLite DB (TEST_DATABASE_URL). CF calls are
monkeypatched — no network is touched.
"""
import asyncio
import json
import logging
import os
import re
import secrets
import sys

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

from app import auth, mailer, models, ratelimit  # noqa: E402
from app.db import Base  # noqa: E402
import app.main as mainmod  # noqa: E402
from app.main import app  # noqa: E402
import app.sync as syncmod  # noqa: E402


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


ORIGIN = "http://localhost:5173"


def _user(db, email="a@test.dev", verified=True):
    u = models.User(email=email, password_hash=auth.hash_password("secret123"),
                    email_verified=verified)
    db.add(u)
    db.commit()
    return u


def _tokens(user_id):
    session = dbmod.SessionLocal()
    try:
        return auth.issue_tokens(session, user_id)
    finally:
        session.close()


def _csrf_token():
    return secrets.token_urlsafe(32)


def _auth_headers(user_id):
    """Cookie-based auth (Batch 6, N4) — same shape as the other files."""
    tokens = _tokens(user_id)
    csrf = _csrf_token()
    cookie = (f"cp_access={tokens['access_token']}; "
              f"cp_refresh={tokens['refresh_token']}; cp_csrf={csrf}")
    return {"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": ORIGIN}


def _anon_headers():
    csrf = _csrf_token()
    return {"Cookie": f"cp_csrf={csrf}", "X-CSRF-Token": csrf, "Origin": ORIGIN}


def _refresh_headers(refresh_token):
    csrf = _csrf_token()
    return {"Cookie": f"cp_refresh={refresh_token}; cp_csrf={csrf}",
            "X-CSRF-Token": csrf, "Origin": ORIGIN}


def _audit_events(caplog, event):
    """Parsed audit records (JSON lines on cpcompass.audit) for one event."""
    out = []
    for rec in caplog.records:
        if rec.name != "cpcompass.audit":
            continue
        try:
            row = json.loads(rec.message)
        except (ValueError, TypeError):
            continue
        if row.get("event") == event:
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# N1 — register rate limit (shared resend bucket) + old code survives
# ---------------------------------------------------------------------------
def test_n1_register_rate_limit_per_email(client, monkeypatch):
    monkeypatch.setattr("app.main.mailer.send_verification_code",
                        lambda email, code: True)
    res = client.post("/api/v1/auth/register",
                      json={"email": "n1@test.dev", "password": "secret123"},
                      headers=_anon_headers())
    assert res.status_code == 201
    # Same email again within a minute -> 429 (shared resend bucket).
    res = client.post("/api/v1/auth/register",
                      json={"email": "n1@test.dev", "password": "secret123"},
                      headers=_anon_headers())
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_n1_old_code_survives_failed_resend(client, monkeypatch):
    captured = {}

    def ok_send(email, code):
        captured["code"] = code
        return True

    monkeypatch.setattr("app.main.mailer.send_verification_code", ok_send)
    res = client.post("/api/v1/auth/register",
                      json={"email": "n1@test.dev", "password": "secret123"},
                      headers=_anon_headers())
    assert res.status_code == 201
    code1 = captured["code"]
    # The mail fails on re-register: the old code must still work.
    monkeypatch.setattr("app.main.mailer.send_verification_code",
                        lambda email, code: False)
    ratelimit.reset()
    res = client.post("/api/v1/auth/register",
                      json={"email": "n1@test.dev", "password": "secret123"},
                      headers=_anon_headers())
    assert res.status_code == 201  # dev: no 503 without a Resend key
    res = client.post("/api/v1/auth/verify-email",
                      json={"email": "n1@test.dev", "code": code1},
                      headers=_anon_headers())
    assert res.status_code == 200
    # A successful re-send replaces the code: the old one dies. This
    # needs a still-UNVERIFIED user: re-registering a verified account
    # issues no code at all (by design — no enumeration, nothing to
    # verify), so the replacement is proven on a second account.
    monkeypatch.setattr("app.main.mailer.send_verification_code", ok_send)
    res = client.post("/api/v1/auth/register",
                      json={"email": "n1b@test.dev", "password": "secret123"},
                      headers=_anon_headers())
    assert res.status_code == 201
    code1b = captured["code"]
    ratelimit.reset()
    res = client.post("/api/v1/auth/register",
                      json={"email": "n1b@test.dev", "password": "secret123"},
                      headers=_anon_headers())
    assert res.status_code == 201
    code2b = captured["code"]
    assert code2b != code1b
    res = client.post("/api/v1/auth/verify-email",
                      json={"email": "n1b@test.dev", "code": code1b},
                      headers=_anon_headers())
    assert res.status_code == 400  # old code died on the re-send
    res = client.post("/api/v1/auth/verify-email",
                      json={"email": "n1b@test.dev", "code": code2b},
                      headers=_anon_headers())
    assert res.status_code == 200
    res = client.post("/api/v1/auth/verify-email",
                      json={"email": "n1@test.dev", "code": code1},
                      headers=_anon_headers())
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# N2 — password recovery
# ---------------------------------------------------------------------------
def _forgot(client, monkeypatch, email):
    """Runs forgot-password, returns the raw reset token from the mail."""
    captured = {}

    def fake_reset(email, reset_url):
        captured["reset_url"] = reset_url
        return True

    monkeypatch.setattr("app.main.mailer.send_password_reset", fake_reset)
    res = client.post("/api/v1/auth/forgot-password",
                      json={"email": email}, headers=_anon_headers())
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert "If an account exists" in res.json()["message"]
    m = re.search(r"token=([A-Za-z0-9_\-]+)", captured["reset_url"])
    assert m, captured
    return m.group(1)


def test_n2_forgot_generic_response_for_unknown_email(client, db):
    # No user exists: same 200 + same message, no token row created.
    res = client.post("/api/v1/auth/forgot-password",
                      json={"email": "ghost@test.dev"}, headers=_anon_headers())
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert "If an account exists" in res.json()["message"]
    assert db.query(models.PasswordResetToken).count() == 0


def test_n2_reset_flow_single_use(client, db, monkeypatch):
    user = _user(db)
    token = _forgot(client, monkeypatch, "a@test.dev")
    # Wrong token -> the same generic 400 as a missing one.
    res = client.post("/api/v1/auth/reset-password",
                      json={"token": "no-such-token",
                            "new_password": "newsecret123"},
                      headers=_anon_headers())
    assert res.status_code == 400
    assert "Invalid or expired" in res.json()["detail"]
    # Right token -> password changes, old password stops working.
    res = client.post("/api/v1/auth/reset-password",
                      json={"token": token, "new_password": "newsecret123"},
                      headers=_anon_headers())
    assert res.status_code == 200
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "secret123"},
                      headers=_anon_headers())
    assert res.status_code == 401
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "newsecret123"},
                      headers=_anon_headers())
    assert res.status_code == 200
    # Single-use: the same token is dead now.
    ratelimit.reset()
    res = client.post("/api/v1/auth/reset-password",
                      json={"token": token, "new_password": "otherpass123"},
                      headers=_anon_headers())
    assert res.status_code == 400


def test_n2_forgot_rate_limit_per_email(client, db, monkeypatch):
    _user(db)
    monkeypatch.setattr("app.main.mailer.send_password_reset",
                        lambda email, reset_url: True)
    res = client.post("/api/v1/auth/forgot-password",
                      json={"email": "a@test.dev"}, headers=_anon_headers())
    assert res.status_code == 200
    res = client.post("/api/v1/auth/forgot-password",
                      json={"email": "a@test.dev"}, headers=_anon_headers())
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_n2_reset_revokes_all_refresh_tokens(client, db, monkeypatch):
    user = _user(db)
    # Log in: capture the live refresh cookie.
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "secret123"},
                      headers=_anon_headers())
    assert res.status_code == 200
    old_refresh = res.cookies["cp_refresh"]
    token = _forgot(client, monkeypatch, "a@test.dev")
    ratelimit.reset()
    res = client.post("/api/v1/auth/reset-password",
                      json={"token": token, "new_password": "newsecret123"},
                      headers=_anon_headers())
    assert res.status_code == 200
    # The pre-reset refresh token no longer refreshes (family revoked).
    res = client.post("/api/v1/auth/refresh",
                      headers=_refresh_headers(old_refresh))
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# N3 — X-Forwarded-For is not trusted
# ---------------------------------------------------------------------------
def test_n3_xff_ignored_in_dev(client, db, caplog):
    caplog.set_level(logging.INFO, logger="cpcompass.audit")
    _user(db)
    # A spoofed XFF must not become the audit IP in dev: the direct
    # peer (TestClient) is the client.
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "wrongpass"},
                      headers={**_anon_headers(),
                               "X-Forwarded-For": "1.2.3.4, 5.6.7.8"})
    assert res.status_code == 401
    events = _audit_events(caplog, "auth.login_failed")
    assert events, "no auth.login_failed audit event"
    assert events[-1]["ip"] == "testclient"
    assert "1.2.3.4" not in str(events[-1])


# ---------------------------------------------------------------------------
# N4 — HttpOnly cookies + CSRF
# ---------------------------------------------------------------------------
def test_n4_login_sets_httponly_cookies_no_tokens_in_body(client, db):
    _user(db)
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "secret123"},
                      headers=_anon_headers())
    assert res.status_code == 200
    body = res.json()
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert "token_type" not in body
    assert body["csrf_token"]
    assert body["email"] == "a@test.dev"
    set_cookie = res.headers.get_list("set-cookie")
    assert len(set_cookie) >= 3
    access = [c for c in set_cookie if c.startswith("cp_access=")]
    refresh = [c for c in set_cookie if c.startswith("cp_refresh=")]
    csrf = [c for c in set_cookie if c.startswith("cp_csrf=")]
    assert access and refresh and csrf
    # Dev (not prod): HttpOnly + SameSite=Lax, no Secure flag.
    assert "HttpOnly" in access[0]
    assert "SameSite=Lax" in access[0] or "samesite=lax" in access[0].lower()
    assert "Secure" not in access[0]
    assert "Path=/" in access[0]
    assert "HttpOnly" in refresh[0]
    assert "/api/v1/auth" in refresh[0]


def test_n4_bearer_header_is_ignored(client, db):
    u = _user(db)
    tokens = _tokens(u.id)
    res = client.get("/api/v1/auth/me",
                     headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert res.status_code == 401


def test_n4_csrf_missing_header_403(client, db):
    u = _user(db)
    tokens = _tokens(u.id)
    headers = {"Cookie": f"cp_access={tokens['access_token']}; "
                         f"cp_refresh={tokens['refresh_token']}; "
                         f"cp_csrf={_csrf_token()}",
               "Origin": ORIGIN}  # no X-CSRF-Token
    res = client.post("/api/v1/settings/public-profile",
                      json={"public": True}, headers=headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "csrf_check_failed"


def test_n4_csrf_wrong_origin_403(client, db):
    u = _user(db)
    csrf = _csrf_token()
    tokens = _tokens(u.id)
    headers = {"Cookie": f"cp_access={tokens['access_token']}; "
                         f"cp_refresh={tokens['refresh_token']}; cp_csrf={csrf}",
               "X-CSRF-Token": csrf, "Origin": "https://evil.example"}
    res = client.post("/api/v1/settings/public-profile",
                      json={"public": True}, headers=headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "csrf_check_failed"


def test_n4_csrf_no_origin_no_referer_403(client, db):
    u = _user(db)
    csrf = _csrf_token()
    tokens = _tokens(u.id)
    headers = {"Cookie": f"cp_access={tokens['access_token']}; "
                         f"cp_refresh={tokens['refresh_token']}; cp_csrf={csrf}",
               "X-CSRF-Token": csrf}  # neither Origin nor Referer
    res = client.post("/api/v1/settings/public-profile",
                      json={"public": True}, headers=headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "csrf_check_failed"


def test_n4_csrf_ok_with_origin(client, db):
    u = _user(db)
    res = client.post("/api/v1/settings/public-profile",
                      json={"public": True}, headers=_auth_headers(u.id))
    assert res.status_code == 200
    assert res.json() == {"public_profile": True}


def test_n4_csrf_endpoint_idempotent(client):
    res = client.get("/api/v1/auth/csrf")
    assert res.status_code == 200
    assert res.json()["csrf_token"]
    assert "no-store" in res.headers.get("cache-control", "")
    assert any(c.startswith("cp_csrf=") for c in res.headers.get_list("set-cookie"))
    token1 = res.json()["csrf_token"]
    res2 = client.get("/api/v1/auth/csrf")
    assert res2.json()["csrf_token"] == token1  # idempotent: same value


def test_n4_cookie_probe_two_calls(client):
    first = client.get("/api/v1/auth/cookie-probe")
    assert first.json() == {"cookies_ok": False}
    second = client.get("/api/v1/auth/cookie-probe")
    assert second.json() == {"cookies_ok": True}


def test_n4_sse_cookie_auth_and_token_param_rejected(client, db):
    u = _user(db)
    tokens = _tokens(u.id)
    # Cookie auth works.
    res = client.get("/api/v1/sync/stream", headers=_auth_headers(u.id))
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    # The ?token= param is dead: a valid token in the URL, no cookie.
    res = client.get(f"/api/v1/sync/stream?token={tokens['access_token']}")
    assert res.status_code == 401
    # ...and a cookie request that also carries ?token= still works
    # (the param is ignored, not an error).
    res = client.get(f"/api/v1/sync/stream?token={tokens['access_token']}",
                     headers=_auth_headers(u.id))
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# #8 — audit logging
# ---------------------------------------------------------------------------
def test_audit_login_failed_lockout_and_429(client, db, caplog):
    caplog.set_level(logging.INFO, logger="cpcompass.audit")
    _user(db)
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "wrongpass"},
                      headers=_anon_headers())
    assert res.status_code == 401
    assert _audit_events(caplog, "auth.login_failed"), "no login_failed event"
    for _ in range(4):
        client.post("/api/v1/auth/login",
                    json={"email": "a@test.dev", "password": "wrongpass"},
                    headers=_anon_headers())
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "secret123"},
                      headers=_anon_headers())
    assert res.status_code == 429
    assert _audit_events(caplog, "auth.login_locked"), "no login_locked event"


def test_audit_rate_limited_429(client, db, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="cpcompass.audit")
    _user(db)
    monkeypatch.setattr("app.main.mailer.send_password_reset",
                        lambda email, reset_url: True)
    client.post("/api/v1/auth/forgot-password",
                json={"email": "a@test.dev"}, headers=_anon_headers())
    res = client.post("/api/v1/auth/forgot-password",
                      json={"email": "a@test.dev"}, headers=_anon_headers())
    assert res.status_code == 429
    events = _audit_events(caplog, "auth.rate_limited")
    assert events, "no rate_limited event"
    assert any(e.get("detail") == "forgot-password" for e in events)


def test_audit_refresh_reuse(client, db, caplog):
    caplog.set_level(logging.INFO, logger="cpcompass.audit")
    user = _user(db)
    tokens = _tokens(user.id)
    res = client.post("/api/v1/auth/refresh",
                      headers=_refresh_headers(tokens["refresh_token"]))
    assert res.status_code == 200
    new_refresh = res.cookies["cp_refresh"]
    assert new_refresh != tokens["refresh_token"]
    res = client.post("/api/v1/auth/refresh",
                      headers=_refresh_headers(tokens["refresh_token"]))
    assert res.status_code == 401
    events = _audit_events(caplog, "auth.refresh_reused")
    assert events, "no refresh_reused event"
    assert events[-1]["user_id"] == user.id


# ---------------------------------------------------------------------------
# Section 8 — rate limits on the four Batch 5 endpoints
# ---------------------------------------------------------------------------
def test_rate_limit_sync_stream(client, db):
    u = _user(db)
    for _ in range(20):
        res = client.get("/api/v1/sync/stream", headers=_auth_headers(u.id))
        assert res.status_code == 200
    res = client.get("/api/v1/sync/stream", headers=_auth_headers(u.id))
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_rate_limit_public_profile_toggle(client, db):
    u = _user(db)
    for i in range(20):
        res = client.post("/api/v1/settings/public-profile",
                          json={"public": i % 2 == 0},
                          headers=_auth_headers(u.id))
        assert res.status_code == 200
    res = client.post("/api/v1/settings/public-profile",
                      json={"public": True}, headers=_auth_headers(u.id))
    assert res.status_code == 429


def test_rate_limit_ics_export(client, db, monkeypatch):
    async def _empty():
        return []

    monkeypatch.setattr(mainmod.cf, "contest_list", _empty)
    u = _user(db)
    for _ in range(30):
        res = client.get("/api/v1/calendar/export.ics",
                         headers=_auth_headers(u.id))
        assert res.status_code == 200
    res = client.get("/api/v1/calendar/export.ics",
                     headers=_auth_headers(u.id))
    assert res.status_code == 429


def test_rate_limit_public_profile_view(client, db):
    u = _user(db)
    db.add(models.CfAccount(user_id=u.id, handle="Khalid_Bin_Masud",
                            handle_norm="khalid_bin_masud"))
    db.commit()
    res = client.post("/api/v1/settings/public-profile",
                      json={"public": True}, headers=_auth_headers(u.id))
    assert res.status_code == 200
    for _ in range(100):
        res = client.get("/api/v1/u/Khalid_Bin_Masud")
        assert res.status_code == 200
    res = client.get("/api/v1/u/Khalid_Bin_Masud")
    assert res.status_code == 429


# ---------------------------------------------------------------------------
# "Synced never" wart — last_synced_at is stamped even with 0 new
# ---------------------------------------------------------------------------
def test_synced_never_wart_zero_new_still_stamps(client, db, monkeypatch):
    u = _user(db)
    db.add(models.CfAccount(user_id=u.id, handle="Khalid_Bin_Masud",
                            handle_norm="khalid_bin_masud"))
    job = models.SyncJob(user_id=u.id, status="pending")
    db.add(job)
    db.commit()
    assert job.last_synced_at is None

    async def _no_subs(handle, start_from=1, count=1000):
        return []

    async def _no_rating(handle):
        return []

    monkeypatch.setattr(syncmod.cf, "user_status", _no_subs)
    monkeypatch.setattr(syncmod.cf, "user_rating", _no_rating)
    asyncio.run(syncmod.run_sync(db, u, job))
    db.refresh(job)
    assert job.status == "done"
    assert job.last_synced_at is not None


# ---------------------------------------------------------------------------
# Mailer outbox shape (N2 reset mail + the verification mail it extends)
# ---------------------------------------------------------------------------
def test_mailer_reset_outbox_shape(tmp_path, monkeypatch):
    outbox = tmp_path / "outbox.log"
    monkeypatch.setattr(mailer, "MAIL_DEV_OUTBOX", str(outbox))
    monkeypatch.setattr(mailer, "RESEND_API_KEY", None)
    ok = mailer.send_password_reset(
        "a@test.dev", "http://localhost:5173/auth/reset?token=abc123")
    assert ok is True
    rows = [json.loads(line) for line in outbox.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["to"] == "a@test.dev"
    assert row["subject"] == "Reset your CP Compass password"
    assert row["reset_url"] == "http://localhost:5173/auth/reset?token=abc123"
    assert row["sent_at"]
    # The verification mail keeps its old shape (code, not reset_url).
    ok = mailer.send_verification_code("a@test.dev", "123456")
    assert ok is True
    rows = [json.loads(line) for line in outbox.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[1]["code"] == "123456"
    assert "reset_url" not in rows[1]
