"""Batch 1 security tests (audit 2026-11-27, findings F1–F10).

F1 handle verification (profile token) — incl. the two-account claim test.
F2 login lockout after 5 failures + 8-char minimum password.
F4 refresh-token reuse detection revokes the whole token family.
F5 ML retrain cooldown (1/hour per user).
F6 email verification code flow + TOTP 2FA setup/login with backup codes.
F7 no account enumeration (register response identical for new/existing).
F8 security headers on responses. F9 ml/status scoped to the caller.
F10 request body size limit (413).

Runs against a throwaway SQLite DB (TEST_DATABASE_URL). CF calls are
monkeypatched — no network is touched.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

os.environ["TEST_DATABASE_URL"] = "sqlite:///./test_cpcompass.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.config as config  # noqa: E402
config.DATABASE_URL = os.environ["TEST_DATABASE_URL"]

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
    mainmod._last_retrain_finished_at = None
    yield
    dbmod.engine.dispose()
    if os.path.exists("test_cpcompass.db"):
        os.remove("test_cpcompass.db")


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


def _auth_headers(user_id):
    tokens = _tokens(user_id)
    return {"Authorization": f"Bearer {tokens['access_token']}"}, tokens


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def db():
    session = dbmod.SessionLocal()
    yield session
    session.close()


def _fake_profile(handle, first_name=""):
    return {"handle": handle, "firstName": first_name, "lastName": "",
            "city": "", "organization": "", "rank": None, "rating": None}


# ---------------------------------------------------------------------------
# F1 — handle verification
# ---------------------------------------------------------------------------
def test_f1_handle_verification_flow(client, db, monkeypatch):
    """Owner flow: start -> token -> token in profile -> confirm -> linked."""
    async def verify(handle):
        return _fake_profile(handle, first_name="CP-AAAAAA")

    monkeypatch.setattr("app.main.cf.verify_handle", verify)
    user = _user(db)
    headers, _ = _auth_headers(user.id)
    res = client.post("/api/v1/auth/handle/start", json={"handle": "tourist"},
                      headers=headers)
    assert res.status_code == 200
    token = res.json()["token"]
    assert token.startswith("CP-") and len(token) == 9
    # Confirm without the token in the profile -> 400.
    async def verify_no_token(handle):
        return _fake_profile(handle, first_name="Tourist")

    monkeypatch.setattr("app.main.cf.verify_handle", verify_no_token)
    res = client.post("/api/v1/auth/handle/confirm", json={"handle": "tourist"},
                      headers=headers)
    assert res.status_code == 400
    assert "Token not found" in res.json()["detail"]
    # Now put the token in the profile -> confirm links the handle.
    async def verify_with_token(handle):
        return _fake_profile(handle, first_name=f"Tourist {token}")

    monkeypatch.setattr("app.main.cf.verify_handle", verify_with_token)
    res = client.post("/api/v1/auth/handle/confirm", json={"handle": "tourist"},
                      headers=headers)
    assert res.status_code == 200
    assert res.json()["cf_handle"] == "tourist"
    assert db.query(models.CfAccount).filter_by(user_id=user.id).one().handle == "tourist"


def test_f1_second_account_cannot_claim_handle(client, db, monkeypatch):
    """Two-account test: B must NOT be able to claim A's handle."""
    async def verify(handle):
        return _fake_profile(handle, first_name="Tourist")

    monkeypatch.setattr("app.main.cf.verify_handle", verify)
    a = _user(db, "a@test.dev")
    b = _user(db, "b@test.dev")
    headers_a, _ = _auth_headers(a.id)
    headers_b, _ = _auth_headers(b.id)
    # A links "tourist" (token in profile).
    res = client.post("/api/v1/auth/handle/start", json={"handle": "tourist"},
                      headers=headers_a)
    token = res.json()["token"]

    async def verify_with_token(handle):
        return _fake_profile(handle, first_name=f"Tourist {token}")

    monkeypatch.setattr("app.main.cf.verify_handle", verify_with_token)
    assert client.post("/api/v1/auth/handle/confirm", json={"handle": "tourist"},
                       headers=headers_a).status_code == 200
    # B tries to start verification for the same handle -> refused.
    res = client.post("/api/v1/auth/handle/start", json={"handle": "tourist"},
                      headers=headers_b)
    assert res.status_code == 400
    assert "already connected" in res.json()["detail"]


def test_f1_confirm_without_start_rejected(client, db):
    user = _user(db)
    headers, _ = _auth_headers(user.id)
    res = client.post("/api/v1/auth/handle/confirm", json={"handle": "tourist"},
                      headers=headers)
    assert res.status_code == 400
    assert "start again" in res.json()["detail"]


# ---------------------------------------------------------------------------
# F2 — login lockout + password length
# ---------------------------------------------------------------------------
def test_f2_login_lockout_after_failures(client, db):
    _user(db)
    for _ in range(5):
        res = client.post("/api/v1/auth/login",
                          json={"email": "a@test.dev", "password": "wrongpass"})
        assert res.status_code == 401
    # 6th attempt — even with the RIGHT password — is locked out.
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "secret123"})
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_f2_password_minimum_8(client):
    res = client.post("/api/v1/auth/register",
                      json={"email": "short@test.dev", "password": "abc1234"})
    assert res.status_code == 422  # 7 chars: rejected by validation
    res = client.post("/api/v1/auth/register",
                      json={"email": "ok@test.dev", "password": "abc12345"})
    assert res.status_code == 201  # 8 chars: accepted


# ---------------------------------------------------------------------------
# F4 — refresh-token reuse detection
# ---------------------------------------------------------------------------
def test_f4_refresh_reuse_revokes_family(client, db):
    user = _user(db)
    tokens = _tokens(user.id)
    res = client.post("/api/v1/auth/refresh",
                      json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 200
    new_refresh = res.json()["refresh_token"]
    # Replaying the OLD (rotated) token -> 401, and the family dies:
    # the NEW token no longer refreshes either.
    res = client.post("/api/v1/auth/refresh",
                      json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 401
    res = client.post("/api/v1/auth/refresh",
                      json={"refresh_token": new_refresh})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# F5 — retrain cooldown
# ---------------------------------------------------------------------------
def test_f5_retrain_cooldown(client, db, monkeypatch):
    monkeypatch.setattr("app.main.ml.train_model",
                        lambda db_: {"trained": True, "sources": {}})
    user = _user(db)
    headers, _ = _auth_headers(user.id)
    res = client.post("/api/v1/ml/retrain", headers=headers)
    assert res.status_code == 200
    res = client.post("/api/v1/ml/retrain", headers=headers)
    assert res.status_code == 429
    assert "once per hour" in res.json()["detail"]


# ---------------------------------------------------------------------------
# F6 — email verification + TOTP 2FA
# ---------------------------------------------------------------------------
def test_f6_email_code_flow(client, db, monkeypatch):
    """Register -> code (captured from the mailer) -> login blocked until
    verified -> wrong code rejected -> right code issues tokens."""
    captured = {}

    def fake_send(email, code):
        captured["code"] = code
        return True

    monkeypatch.setattr("app.main.mailer.send_verification_code", fake_send)
    res = client.post("/api/v1/auth/register",
                      json={"email": "new@test.dev", "password": "secret123"})
    assert res.status_code == 201
    assert res.json()["verification_required"] is True
    assert "code" in captured
    # Login before verification -> 403, no tokens.
    res = client.post("/api/v1/auth/login",
                      json={"email": "new@test.dev", "password": "secret123"})
    assert res.status_code == 403
    # Wrong code -> 400.
    res = client.post("/api/v1/auth/verify-email",
                      json={"email": "new@test.dev", "code": "000000"})
    assert res.status_code == 400
    # Right code -> tokens.
    res = client.post("/api/v1/auth/verify-email",
                      json={"email": "new@test.dev", "code": captured["code"]})
    assert res.status_code == 200
    assert res.json()["access_token"]
    # Same code again -> already used.
    res = client.post("/api/v1/auth/verify-email",
                      json={"email": "new@test.dev", "code": captured["code"]})
    assert res.status_code == 400
    # Login now works.
    res = client.post("/api/v1/auth/login",
                      json={"email": "new@test.dev", "password": "secret123"})
    assert res.status_code == 200


def test_f6_totp_setup_login_and_backup_codes(client, db):
    import pyotp

    user = _user(db)
    headers, _ = _auth_headers(user.id)
    res = client.post("/api/v1/auth/2fa/setup", headers=headers)
    assert res.status_code == 200
    secret = res.json()["secret"]
    assert res.json()["otpauth_uri"].startswith("otpauth://totp/")
    # Wrong code cannot enable 2FA.
    res = client.post("/api/v1/auth/2fa/enable", json={"code": "000000"},
                      headers=headers)
    assert res.status_code == 400
    # Right code enables it and returns 10 backup codes, once.
    code = pyotp.TOTP(secret).now()
    res = client.post("/api/v1/auth/2fa/enable", json={"code": code},
                      headers=headers)
    assert res.status_code == 200
    backup_codes = res.json()["backup_codes"]
    assert len(backup_codes) == 10
    # Login now stops at the second factor.
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "secret123"})
    assert res.status_code == 200
    assert res.json()["totp_required"] is True
    pre_token = res.json()["pre_token"]
    # Wrong second-factor code -> 401.
    res = client.post("/api/v1/auth/2fa/verify",
                      json={"pre_token": pre_token, "code": "000000"})
    assert res.status_code == 401
    # Right TOTP code -> tokens.
    res = client.post("/api/v1/auth/2fa/verify",
                      json={"pre_token": pre_token,
                            "code": pyotp.TOTP(secret).now()})
    assert res.status_code == 200
    assert res.json()["access_token"]
    # Backup code works once, then dies.
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "secret123"})
    pre_token = res.json()["pre_token"]
    res = client.post("/api/v1/auth/2fa/verify",
                      json={"pre_token": pre_token, "code": backup_codes[0]})
    assert res.status_code == 200
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "secret123"})
    pre_token = res.json()["pre_token"]
    res = client.post("/api/v1/auth/2fa/verify",
                      json={"pre_token": pre_token, "code": backup_codes[0]})
    assert res.status_code == 401
    # Disable needs the password; afterwards login is single-step again.
    res = client.post("/api/v1/auth/2fa/disable",
                      json={"password": "wrongpass"}, headers=headers)
    assert res.status_code == 401
    res = client.post("/api/v1/auth/2fa/disable",
                      json={"password": "secret123"}, headers=headers)
    assert res.status_code == 200
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "secret123"})
    assert res.status_code == 200
    assert "totp_required" not in res.json()


# ---------------------------------------------------------------------------
# F7 — no enumeration
# ---------------------------------------------------------------------------
def test_f7_register_response_identical_for_existing_email(client, db):
    _user(db, "a@test.dev")
    before = db.query(models.User).count()
    res = client.post("/api/v1/auth/register",
                      json={"email": "a@test.dev", "password": "secret123"})
    assert res.status_code == 201
    assert res.json()["verification_required"] is True
    assert db.query(models.User).count() == before  # no duplicate user
    # Login with a wrong email costs the same as a wrong password: 401,
    # never 404.
    res = client.post("/api/v1/auth/login",
                      json={"email": "nobody@test.dev", "password": "secret123"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# F8 / F9 / F10
# ---------------------------------------------------------------------------
def test_f8_security_headers(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["Referrer-Policy"] == "no-referrer"


def test_f9_ml_status_scoped_to_caller(client, db, monkeypatch):
    fake = {"model": None, "feature_names": [], "top_tags": [],
            "metadata": {
                "model_type": "test", "trained_at": "2026-01-01T00:00:00Z",
                "n_rows": 80, "n_solved": 50,
                "sources": {"alice": 50, "bob": 30},
                "demo_rows": 0, "real_rows": 80, "features": [],
                "shipped": True, "ship_reason": "test", "bias_note": "test",
                "evaluation": {"baseline": {}, "random_forest": {},
                               "logreg": {}, "hist_gb": {},
                               "calibration": {}}}}
    monkeypatch.setattr("app.ml._load_artifact", lambda: fake)
    alice = _user(db, "alice@test.dev")
    bob = _user(db, "bob@test.dev")
    db.add(models.CfAccount(user_id=alice.id, handle="alice",
                            handle_norm="alice"))
    db.add(models.CfAccount(user_id=bob.id, handle="bob", handle_norm="bob"))
    db.commit()
    headers_a, _ = _auth_headers(alice.id)
    headers_b, _ = _auth_headers(bob.id)
    res = client.get("/api/v1/ml/status", headers=headers_a)
    assert res.status_code == 200
    assert res.json()["sources"] == {"alice": 50}
    res = client.get("/api/v1/ml/status", headers=headers_b)
    assert res.json()["sources"] == {"bob": 30}
    # Demo: aggregates only, no handles at all.
    res = client.get("/api/v1/demo/ml/status")
    assert res.status_code == 200
    assert res.json()["sources"] == {}


def test_f10_body_size_limit(client):
    big = "x" * 1_200_000
    res = client.post("/api/v1/auth/register",
                      json={"email": f"{big}@test.dev", "password": "secret123"})
    assert res.status_code == 413


def test_delete_account_requires_password(client, db):
    user = _user(db)
    headers, _ = _auth_headers(user.id)
    res = client.request("DELETE", "/api/v1/auth/account",
                         json={"password": "wrongpass"}, headers=headers)
    assert res.status_code == 401
    assert db.query(models.User).filter_by(id=user.id).one_or_none() is not None
    res = client.request("DELETE", "/api/v1/auth/account",
                         json={"password": "secret123"}, headers=headers)
    assert res.status_code == 200
    assert db.query(models.User).filter_by(id=user.id).one_or_none() is None
