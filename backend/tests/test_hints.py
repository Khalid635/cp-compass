"""AI Hint Ladder tests (batch ai-hint-ladder).

Runs against a throwaway SQLite DB (TEST_DATABASE_URL). Gemini is
monkeypatched — no network is touched. Covers: not-configured 503,
happy path step 1, step order enforcement, cache (second call free),
daily limit 429, Gemini failure 502, unknown problem 404, solved
problem 400, prompt guardrails, auth required, GET unlocked list,
language regeneration.
"""
import os
import sys
from datetime import datetime

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

from app import auth, hints, models, ratelimit  # noqa: E402
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


@pytest.fixture()
def configured(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-3.5-flash")
    monkeypatch.setattr(config, "HINT_DAILY_LIMIT", 10)


def _user(db, email="a@test.dev", verified=True):
    u = models.User(email=email,
                    password_hash=auth.hash_password("secret123"),
                    email_verified=verified, current_rating=1400)
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
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _problem(db, contest_id=1360, index="E", name="Polygon", rating=1400):
    p = models.Problem(contest_id=contest_id, index=index, name=name,
                       rating=rating, tags=["implementation", "math"])
    db.add(p)
    db.commit()
    return p


def _submission(db, user_id, problem_id, verdict="WRONG_ANSWER",
                passed=2):
    s = models.Submission(cf_submission_id=1000 + problem_id,
                          user_id=user_id, problem_id=problem_id,
                          verdict=verdict, language="C++17",
                          submitted_at=datetime.utcnow(),
                          passed_test_count=passed)
    db.add(s)
    db.commit()
    return s


def _mock_gemini(monkeypatch, text="Look at the constraints first."):
    calls = {"n": 0}

    def fake(prompt):
        calls["n"] += 1
        return text

    monkeypatch.setattr(hints, "_call_gemini", fake)
    return calls


def test_hints_not_configured_503(client, db, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    u = _user(db)
    _problem(db)
    r = client.post("/api/v1/problems/1360/E/hints",
                    json={"step": 1, "lang": "en"},
                    headers=_auth_headers(u.id))
    assert r.status_code == 503


def test_hints_happy_path_step1(client, db, configured, monkeypatch):
    u = _user(db)
    _problem(db)
    _mock_gemini(monkeypatch, "Notice the polygon vertices are given in order.")
    r = client.post("/api/v1/problems/1360/E/hints",
                    json={"step": 1, "lang": "en"},
                    headers=_auth_headers(u.id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["step"] == 1
    assert body["text"] == "Notice the polygon vertices are given in order."
    assert body["cached"] is False
    assert body["used_today"] == 1
    assert body["limit"] == 10


def test_hints_step2_requires_step1(client, db, configured, monkeypatch):
    u = _user(db)
    _problem(db)
    _mock_gemini(monkeypatch)
    r = client.post("/api/v1/problems/1360/E/hints",
                    json={"step": 2, "lang": "en"},
                    headers=_auth_headers(u.id))
    assert r.status_code == 400


def test_hints_cache_second_call_free(client, db, configured, monkeypatch):
    u = _user(db)
    _problem(db)
    calls = _mock_gemini(monkeypatch)
    h = _auth_headers(u.id)
    r1 = client.post("/api/v1/problems/1360/E/hints",
                     json={"step": 1, "lang": "en"}, headers=h)
    r2 = client.post("/api/v1/problems/1360/E/hints",
                     json={"step": 1, "lang": "en"}, headers=h)
    assert r1.status_code == 200 and r2.status_code == 200
    assert calls["n"] == 1
    assert r2.json()["cached"] is True
    assert r2.json()["used_today"] == 1


def test_hints_daily_limit_429(client, db, configured, monkeypatch):
    monkeypatch.setattr(config, "HINT_DAILY_LIMIT", 2)
    u = _user(db)
    _problem(db)
    _mock_gemini(monkeypatch)
    h = _auth_headers(u.id)
    assert client.post("/api/v1/problems/1360/E/hints",
                       json={"step": 1, "lang": "en"}, headers=h).status_code == 200
    assert client.post("/api/v1/problems/1360/E/hints",
                       json={"step": 2, "lang": "en"}, headers=h).status_code == 200
    r = client.post("/api/v1/problems/1360/E/hints",
                    json={"step": 3, "lang": "en"}, headers=h)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_hints_gemini_failure_502(client, db, configured, monkeypatch):
    u = _user(db)
    _problem(db)

    def boom(prompt):
        raise hints.HintError("down")

    monkeypatch.setattr(hints, "_call_gemini", boom)
    r = client.post("/api/v1/problems/1360/E/hints",
                    json={"step": 1, "lang": "en"},
                    headers=_auth_headers(u.id))
    assert r.status_code == 502


def test_hints_unknown_problem_404(client, db, configured, monkeypatch):
    u = _user(db)

    async def _empty():
        return []

    monkeypatch.setattr(mainmod.cf, "problemset", _empty)
    r = client.post("/api/v1/problems/9999/Z/hints",
                    json={"step": 1, "lang": "en"},
                    headers=_auth_headers(u.id))
    assert r.status_code == 404


def test_hints_solved_problem_400(client, db, configured, monkeypatch):
    u = _user(db)
    p = _problem(db)
    _submission(db, u.id, p.id, verdict="OK", passed=10)
    _mock_gemini(monkeypatch)
    r = client.post("/api/v1/problems/1360/E/hints",
                    json={"step": 1, "lang": "en"},
                    headers=_auth_headers(u.id))
    assert r.status_code == 400


def test_hints_prompt_guardrails():
    problem = {"contest_id": 1360, "index": "E", "name": "Polygon",
               "rating": 1400, "tags": ["implementation", "math"]}
    detail = {"attempts": 2, "wrong_attempts": 2, "solved": False,
              "submissions": [{"verdict": "WRONG_ANSWER", "language": "C++17",
                               "passed_test_count": 2}]}
    p1 = hints.build_prompt(problem, detail, 1400, 1, "en")
    assert "Never give the full solution" in p1
    assert "Never write code or pseudocode" in p1
    assert "key insight" not in p1  # step 1 must not leak the step 3 content
    p3 = hints.build_prompt(problem, detail, 1400, 3, "en")
    assert "key insight" in p3
    pbn = hints.build_prompt(problem, detail, 1400, 1, "bn")
    assert "Bangla" in pbn


def test_hints_auth_required(client, db, configured):
    _problem(db)
    r = client.post("/api/v1/problems/1360/E/hints",
                    json={"step": 1, "lang": "en"})
    assert r.status_code == 401


def test_hints_get_returns_unlocked(client, db, configured, monkeypatch):
    u = _user(db)
    _problem(db)
    _mock_gemini(monkeypatch)
    h = _auth_headers(u.id)
    client.post("/api/v1/problems/1360/E/hints",
                json={"step": 1, "lang": "en"}, headers=h)
    r = client.get("/api/v1/problems/1360/E/hints", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is True
    assert [x["step"] for x in body["hints"]] == [1]
    assert body["used_today"] == 1
    assert body["limit"] == 10


def test_hints_language_regeneration(client, db, configured, monkeypatch):
    u = _user(db)
    _problem(db)
    calls = {"n": 0}

    def fake(prompt):
        calls["n"] += 1
        return "BN hint" if "Bangla" in prompt else "EN hint"

    monkeypatch.setattr(hints, "_call_gemini", fake)
    h = _auth_headers(u.id)
    r1 = client.post("/api/v1/problems/1360/E/hints",
                     json={"step": 1, "lang": "en"}, headers=h)
    r2 = client.post("/api/v1/problems/1360/E/hints",
                     json={"step": 1, "lang": "bn"}, headers=h)
    assert r1.json()["text"] == "EN hint"
    assert r2.json()["text"] == "BN hint"
    assert r2.json()["cached"] is False
    assert calls["n"] == 2
    assert r2.json()["used_today"] == 2
