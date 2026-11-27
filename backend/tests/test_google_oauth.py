"""Google OAuth sign-in tests (batch google-oauth).

Runs against a throwaway SQLite DB (TEST_DATABASE_URL). Google is
monkeypatched — no network is touched. Covers: not-configured 503,
auth URL + signed state, bad/expired state, new-user creation,
linking an existing password account (password login still works),
duplicate-Google-account guard, unverified Google email, exchange
failure, Google-only password login 401, TOTP second step.
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time

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

from app import auth, google_oauth, models, ratelimit  # noqa: E402
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


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def db():
    session = dbmod.SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def configured(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(
        config, "GOOGLE_REDIRECT_URI", "http://localhost:5173/auth/callback")


def _user(db, email="a@test.dev", verified=True, password="secret123"):
    u = models.User(email=email,
                    password_hash=auth.hash_password(password) if password else None,
                    email_verified=verified)
    db.add(u)
    db.commit()
    return u


def _fake_google(sub="google-sub-1", email="a@test.dev", verified=True):
    def fake_exchange(code):
        assert code == "good-code"
        return {"access_token": "google-access-token", "token_type": "Bearer",
                "expires_in": 3600}

    def fake_userinfo(access_token):
        assert access_token == "google-access-token"
        return {"sub": sub, "email": email, "email_verified": verified,
                "name": "Test User"}

    return fake_exchange, fake_userinfo


def _mock_google(monkeypatch, sub="google-sub-1", email="a@test.dev",
                 verified=True):
    exchange, userinfo = _fake_google(sub, email, verified)
    monkeypatch.setattr(google_oauth, "exchange_code", exchange)
    monkeypatch.setattr(google_oauth, "fetch_userinfo", userinfo)


def _expired_state():
    payload = {"exp": int(time.time()) - 60, "nonce": "old-nonce"}
    data = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
    sig = hmac.new(config.SECRET_KEY.encode(), data.encode(),
                   hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def test_google_not_configured(client):
    res = client.get("/api/v1/auth/google")
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"]


def test_google_auth_url(client, configured):
    res = client.get("/api/v1/auth/google")
    assert res.status_code == 200
    url = res.json()["auth_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "client_id=test-client-id" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A5173%2Fauth%2Fcallback" in url
    assert "scope=openid+email+profile" in url or "scope=openid%20email%20profile" in url
    assert "response_type=code" in url
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(url).query)["state"][0]
    assert google_oauth.verify_state(state) is True
    assert google_oauth.verify_state(state[:-1] + ("0" if state[-1] != "0" else "1")) is False
    assert google_oauth.verify_state(_expired_state()) is False


def test_callback_bad_state(client, configured):
    res = client.post("/api/v1/auth/google/callback",
                      json={"code": "good-code", "state": "garbage"})
    assert res.status_code == 400


def test_callback_new_user(client, db, configured, monkeypatch):
    _mock_google(monkeypatch)
    state = google_oauth.build_state()
    res = client.post("/api/v1/auth/google/callback",
                      json={"code": "good-code", "state": state})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["email"] == "a@test.dev"
    assert body["access_token"] and body["refresh_token"]
    user = db.query(models.User).filter_by(email="a@test.dev").first()
    assert user is not None
    assert user.email_verified is True
    assert user.google_id == "google-sub-1"
    assert user.password_hash is None


def test_callback_links_existing_password_user(client, db, configured, monkeypatch):
    user = _user(db, email="a@test.dev", verified=True)
    old_hash = user.password_hash
    _mock_google(monkeypatch)
    state = google_oauth.build_state()
    res = client.post("/api/v1/auth/google/callback",
                      json={"code": "good-code", "state": state})
    assert res.status_code == 200, res.text
    db.expire_all()
    linked = db.query(models.User).filter_by(email="a@test.dev").first()
    assert linked.id == user.id
    assert linked.google_id == "google-sub-1"
    assert linked.email_verified is True
    assert linked.password_hash == old_hash
    # Password login still works for the linked account.
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "secret123"})
    assert res.status_code == 200, res.text
    assert res.json()["email"] == "a@test.dev"


def test_callback_links_unverified_password_user(client, db, configured, monkeypatch):
    user = _user(db, email="a@test.dev", verified=False)
    _mock_google(monkeypatch)
    state = google_oauth.build_state()
    res = client.post("/api/v1/auth/google/callback",
                      json={"code": "good-code", "state": state})
    assert res.status_code == 200, res.text
    db.expire_all()
    linked = db.query(models.User).filter_by(email="a@test.dev").first()
    assert linked.id == user.id
    assert linked.email_verified is True


def test_callback_duplicate_google_account(client, db, configured, monkeypatch):
    user = _user(db, email="a@test.dev")
    user.google_id = "google-sub-1"
    db.commit()
    _mock_google(monkeypatch, sub="google-sub-2", email="a@test.dev")
    state = google_oauth.build_state()
    res = client.post("/api/v1/auth/google/callback",
                      json={"code": "good-code", "state": state})
    assert res.status_code == 400
    assert "different Google account" in res.json()["detail"]


def test_callback_unverified_google_email(client, configured, monkeypatch):
    _mock_google(monkeypatch, verified=False)
    state = google_oauth.build_state()
    res = client.post("/api/v1/auth/google/callback",
                      json={"code": "good-code", "state": state})
    assert res.status_code == 400
    assert "verified email" in res.json()["detail"]


def test_callback_exchange_failure(client, configured, monkeypatch):
    def boom(code):
        raise google_oauth.GoogleOAuthError("token request failed: 400")

    monkeypatch.setattr(google_oauth, "exchange_code", boom)
    state = google_oauth.build_state()
    res = client.post("/api/v1/auth/google/callback",
                      json={"code": "good-code", "state": state})
    assert res.status_code == 502


def test_google_only_user_password_login_401(client, db, configured, monkeypatch):
    _mock_google(monkeypatch)
    state = google_oauth.build_state()
    res = client.post("/api/v1/auth/google/callback",
                      json={"code": "good-code", "state": state})
    assert res.status_code == 200
    res = client.post("/api/v1/auth/login",
                      json={"email": "a@test.dev", "password": "anything123"})
    assert res.status_code == 401


def test_callback_totp_user(client, db, configured, monkeypatch):
    user = _user(db, email="a@test.dev")
    user.totp_enabled = True
    db.commit()
    _mock_google(monkeypatch)
    state = google_oauth.build_state()
    res = client.post("/api/v1/auth/google/callback",
                      json={"code": "good-code", "state": state})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("totp_required") is True
    assert body.get("pre_token")
    assert "access_token" not in body
