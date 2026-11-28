"""Contest post-mortem tests (batch 4).

Runs against a throwaway SQLite DB (TEST_DATABASE_URL). Gemini and the
Codeforces contest list are monkeypatched - no network is touched.
Covers: computation (counts, verdicts, time spent, per-problem rows,
unsolved, weak topics, empty state, list ordering), endpoints (auth,
list, latest, detail 200 has_data false for a known contest with no
submissions, unknown contest 404, CF down 502, demo endpoints), AI
(not-configured 503, happy path, cache second call free, daily limit
429, Gemini failure 502, no-data 400, prompt guardrails, GET cached,
language regeneration).
"""
import os
import sys
from datetime import datetime, timedelta

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

from app import auth, models, postmortem_ai, ratelimit, services  # noqa: E402
from app.cf import CFError  # noqa: E402
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
    monkeypatch.setattr(config, "POSTMORTEM_DAILY_LIMIT", 5)


@pytest.fixture()
def contests(monkeypatch):
    async def _list():
        return [
            {"id": 4, "name": "Codeforces Beta Round #4"},
            {"id": 231, "name": "Codeforces Round #231 (Div. 2)"},
            {"id": 2292, "name": "Codeforces Round #1138 (Div. 3)"},
        ]

    monkeypatch.setattr(mainmod.cf, "contest_list", _list)


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


_sid = [1000]


def _problem(db, contest_id=231, index="A", name="Team", rating=800,
             tags=None):
    p = models.Problem(contest_id=contest_id, index=index, name=name,
                       rating=rating, tags=tags or ["implementation"])
    db.add(p)
    db.commit()
    return p


def _submission(db, user_id, problem_id, verdict="WRONG_ANSWER",
                passed=2, when=None):
    _sid[0] += 1
    s = models.Submission(cf_submission_id=_sid[0],
                          user_id=user_id, problem_id=problem_id,
                          verdict=verdict, language="C++17",
                          submitted_at=when or datetime.utcnow(),
                          passed_test_count=passed)
    db.add(s)
    db.commit()
    return s


def _mock_gemini(monkeypatch, text="Good start, but the WA pattern is clear."):
    calls = {"n": 0}

    def fake(prompt):
        calls["n"] += 1
        return text

    monkeypatch.setattr(postmortem_ai, "_call_gemini", fake)
    return calls


def _rows():
    """231-style rows: problem A solved after one WA, problem B unsolved."""
    t0 = datetime(2026, 7, 23, 10, 0)
    return [
        {"verdict": "WRONG_ANSWER", "passed_test_count": 1,
         "problem": {"contest_id": 231, "index": "A", "name": "Team",
                     "rating": 800, "tags": ["implementation"]},
         "submitted_at": t0},
        {"verdict": "OK", "passed_test_count": 10,
         "problem": {"contest_id": 231, "index": "A", "name": "Team",
                     "rating": 800, "tags": ["implementation"]},
         "submitted_at": t0 + timedelta(minutes=12)},
        {"verdict": "WRONG_ANSWER", "passed_test_count": 0,
         "problem": {"contest_id": 231, "index": "B", "name": "Queue",
                     "rating": 900, "tags": ["implementation", "queue"]},
         "submitted_at": t0 + timedelta(minutes=30)},
    ]


# --- computation ---

def test_compute_postmortem_empty():
    r = services._compute_postmortem([], 2292, "Codeforces Round #1138 (Div. 3)")
    assert r["has_data"] is False
    assert r["attempted"] == 0
    assert r["solved"] == 0
    assert r["total_submissions"] == 0
    assert r["per_problem"] == []
    assert r["unsolved"] == []
    assert r["time_spent_minutes"] is None


def test_compute_postmortem_counts():
    r = services._compute_postmortem(_rows(), 231, "Codeforces Round #231 (Div. 2)")
    assert r["has_data"] is True
    assert r["attempted"] == 2
    assert r["solved"] == 1
    assert r["total_submissions"] == 3
    assert r["verdict_breakdown"] == [
        {"verdict": "WRONG_ANSWER", "count": 2},
        {"verdict": "OK", "count": 1},
    ]
    assert r["time_spent_minutes"] == 30.0
    a, b = r["per_problem"]
    assert a["problem"]["index"] == "A"
    assert a["attempts"] == 2 and a["wrong_attempts"] == 1 and a["solved"] is True
    assert a["minutes_to_solve"] == 12.0
    assert b["problem"]["index"] == "B"
    assert b["solved"] is False and b["minutes_to_solve"] is None
    assert [p["index"] for p in r["unsolved"]] == ["B"]
    assert "queue" in r["practice_next_week"]["topics"]
    assert [p["index"] for p in r["practice_next_week"]["problems"]] == ["B"]


def test_compute_postmortem_weak_topics():
    rows = []
    t0 = datetime(2026, 7, 23, 10, 0)
    for i, (idx, solved) in enumerate([("A", True), ("B", False),
                                       ("C", False)]):
        rows.append({
            "verdict": "OK" if solved else "WRONG_ANSWER",
            "passed_test_count": 5 if solved else 1,
            "problem": {"contest_id": 231, "index": idx, "name": idx,
                        "rating": 1000, "tags": ["dp", "graphs"]},
            "submitted_at": t0 + timedelta(minutes=i * 10)})
    r = services._compute_postmortem(rows, 231)
    assert r["weak_topics"] == [
        {"tag": "dp", "attempted": 3, "solved": 1, "acceptance": 0.33},
        {"tag": "graphs", "attempted": 3, "solved": 1, "acceptance": 0.33},
    ]
    assert r["practice_next_week"]["topics"][:2] == ["dp", "graphs"]


def test_compute_postmortem_list_order():
    t0 = datetime(2026, 7, 23, 10, 0)
    rows = [{
        "verdict": "OK", "passed_test_count": 5,
        "problem": {"contest_id": 231, "index": "A", "name": "Team",
                    "rating": 800, "tags": ["implementation"]},
        "submitted_at": t0},
        {"verdict": "OK", "passed_test_count": 5,
         "problem": {"contest_id": 4, "index": "A", "name": "Watermelon",
                     "rating": 800, "tags": ["implementation"]},
         "submitted_at": t0 + timedelta(days=1)}]
    out = services._compute_postmortem_list(rows, {4: "Beta #4", 231: "Round #231"})
    assert [r["contest_id"] for r in out] == [4, 231]
    assert out[0]["contest_name"] == "Beta #4"
    assert out[0]["solved"] == 1 and out[0]["attempted"] == 1


# --- endpoints ---

def test_postmortems_auth_required(client, contests):
    assert client.get("/api/v1/postmortems").status_code == 401


def test_postmortems_needs_handle(client, db, contests):
    u = _user(db)
    r = client.get("/api/v1/postmortems", headers=_auth_headers(u.id))
    assert r.status_code == 400


def test_postmortems_list_and_latest(client, db, contests):
    u = _user(db)
    _handle(db, u.id)
    t0 = datetime(2026, 7, 23, 10, 0)
    pa = _problem(db, 231, "A", "Team")
    pb = _problem(db, 4, "A", "Watermelon")
    _submission(db, u.id, pa.id, "WRONG_ANSWER", 1, t0)
    _submission(db, u.id, pa.id, "OK", 10, t0 + timedelta(minutes=12))
    _submission(db, u.id, pb.id, "OK", 5, t0 + timedelta(days=1))
    h = _auth_headers(u.id)
    r = client.get("/api/v1/postmortems", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()
    assert [x["contest_id"] for x in items] == [4, 231]
    assert items[0]["contest_name"] == "Codeforces Beta Round #4"
    assert items[1]["solved"] == 1 and items[1]["attempted"] == 1
    r = client.get("/api/v1/postmortems/latest", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["contest_id"] == 4
    assert r.json()["has_data"] is True


def test_postmortems_latest_empty_404(client, db, contests):
    u = _user(db)
    _handle(db, u.id)
    r = client.get("/api/v1/postmortems/latest", headers=_auth_headers(u.id))
    assert r.status_code == 404


def test_postmortem_detail_known_no_data_200(client, db, contests):
    # Round 1138 (2292): a known contest Khalid did not play - honest
    # empty state, never a fabricated report.
    u = _user(db)
    _handle(db, u.id)
    r = client.get("/api/v1/postmortems/2292", headers=_auth_headers(u.id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_data"] is False
    assert body["contest_name"] == "Codeforces Round #1138 (Div. 3)"
    assert body["attempted"] == 0


def test_postmortem_detail_unknown_404(client, db, contests):
    u = _user(db)
    _handle(db, u.id)
    r = client.get("/api/v1/postmortems/999999", headers=_auth_headers(u.id))
    assert r.status_code == 404


def test_postmortem_detail_cf_down_502(client, db, monkeypatch):
    u = _user(db)
    _handle(db, u.id)

    async def _down():
        raise CFError("boom")

    monkeypatch.setattr(mainmod.cf, "contest_list", _down)
    r = client.get("/api/v1/postmortems/231", headers=_auth_headers(u.id))
    assert r.status_code == 502


def test_demo_postmortems(client):
    r = client.get("/api/v1/demo/postmortems")
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) > 0
    assert items[0]["solved"] >= 0
    first = items[0]["contest_id"]
    r = client.get(f"/api/v1/demo/postmortems/{first}")
    assert r.status_code == 200, r.text
    assert r.json()["has_data"] is True
    r = client.get("/api/v1/demo/postmortems/latest")
    assert r.status_code == 200
    assert r.json()["contest_id"] == first
    r = client.get("/api/v1/demo/postmortems/999999")
    assert r.status_code == 404


# --- AI analysis ---

def test_analysis_not_configured_503(client, db, contests, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    u = _user(db)
    _handle(db, u.id)
    p = _problem(db, 231, "A", "Team")
    _submission(db, u.id, p.id, "OK", 10)
    r = client.post("/api/v1/postmortems/231/analysis",
                    json={"lang": "en"}, headers=_auth_headers(u.id))
    assert r.status_code == 503


def test_analysis_happy_path(client, db, contests, configured, monkeypatch):
    u = _user(db)
    _handle(db, u.id)
    p = _problem(db, 231, "A", "Team")
    _submission(db, u.id, p.id, "OK", 10)
    _mock_gemini(monkeypatch, "Solid contest: one clean solve.")
    r = client.post("/api/v1/postmortems/231/analysis",
                    json={"lang": "en"}, headers=_auth_headers(u.id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == "Solid contest: one clean solve."
    assert body["cached"] is False
    assert body["used_today"] == 1
    assert body["limit"] == 5


def test_analysis_cache_second_call_free(client, db, contests, configured,
                                         monkeypatch):
    u = _user(db)
    _handle(db, u.id)
    p = _problem(db, 231, "A", "Team")
    _submission(db, u.id, p.id, "OK", 10)
    calls = _mock_gemini(monkeypatch)
    h = _auth_headers(u.id)
    r1 = client.post("/api/v1/postmortems/231/analysis",
                     json={"lang": "en"}, headers=h)
    r2 = client.post("/api/v1/postmortems/231/analysis",
                     json={"lang": "en"}, headers=h)
    assert r1.status_code == 200 and r2.status_code == 200
    assert calls["n"] == 1
    assert r2.json()["cached"] is True
    assert r2.json()["used_today"] == 1


def test_analysis_daily_limit_429(client, db, contests, configured, monkeypatch):
    monkeypatch.setattr(config, "POSTMORTEM_DAILY_LIMIT", 1)
    u = _user(db)
    _handle(db, u.id)
    pa = _problem(db, 231, "A", "Team")
    pb = _problem(db, 4, "A", "Watermelon")
    _submission(db, u.id, pa.id, "OK", 10)
    _submission(db, u.id, pb.id, "OK", 5)
    _mock_gemini(monkeypatch)
    h = _auth_headers(u.id)
    assert client.post("/api/v1/postmortems/231/analysis",
                       json={"lang": "en"}, headers=h).status_code == 200
    r = client.post("/api/v1/postmortems/4/analysis",
                    json={"lang": "en"}, headers=h)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_analysis_gemini_failure_502(client, db, contests, configured, monkeypatch):
    u = _user(db)
    _handle(db, u.id)
    p = _problem(db, 231, "A", "Team")
    _submission(db, u.id, p.id, "OK", 10)

    def boom(prompt):
        raise postmortem_ai.PostmortemError("down")

    monkeypatch.setattr(postmortem_ai, "_call_gemini", boom)
    r = client.post("/api/v1/postmortems/231/analysis",
                    json={"lang": "en"}, headers=_auth_headers(u.id))
    assert r.status_code == 502


def test_analysis_no_data_400(client, db, contests, configured, monkeypatch):
    u = _user(db)
    _handle(db, u.id)
    _mock_gemini(monkeypatch)
    r = client.post("/api/v1/postmortems/2292/analysis",
                    json={"lang": "en"}, headers=_auth_headers(u.id))
    assert r.status_code == 400


def test_analysis_prompt_guardrails():
    report = services._compute_postmortem(_rows(), 231, "Round #231")
    p = postmortem_ai.build_prompt(report, None, 1400, "en")
    assert "Never give a full solution" in p
    assert "Never write code or pseudocode" in p
    assert "Never link the editorial" in p
    assert "Team" in p and "Queue" in p
    assert "Round #231" in p
    pbn = postmortem_ai.build_prompt(report, None, 1400, "bn")
    assert "Bangla" in pbn


def test_analysis_get_returns_cached(client, db, contests, configured, monkeypatch):
    u = _user(db)
    _handle(db, u.id)
    p = _problem(db, 231, "A", "Team")
    _submission(db, u.id, p.id, "OK", 10)
    _mock_gemini(monkeypatch, "Cached analysis text.")
    h = _auth_headers(u.id)
    r = client.get("/api/v1/postmortems/231/analysis", headers=h)
    assert r.status_code == 200
    assert r.json()["analysis"] is None
    assert r.json()["configured"] is True
    assert r.json()["limit"] == 5
    client.post("/api/v1/postmortems/231/analysis",
                json={"lang": "en"}, headers=h)
    r = client.get("/api/v1/postmortems/231/analysis", headers=h)
    assert r.json()["analysis"] == "Cached analysis text."
    assert r.json()["used_today"] == 1


def test_analysis_language_regeneration(client, db, contests, configured,
                                        monkeypatch):
    u = _user(db)
    _handle(db, u.id)
    p = _problem(db, 231, "A", "Team")
    _submission(db, u.id, p.id, "OK", 10)
    calls = {"n": 0}

    def fake(prompt):
        calls["n"] += 1
        return "BN analysis" if "Bangla" in prompt else "EN analysis"

    monkeypatch.setattr(postmortem_ai, "_call_gemini", fake)
    h = _auth_headers(u.id)
    r1 = client.post("/api/v1/postmortems/231/analysis",
                     json={"lang": "en"}, headers=h)
    r2 = client.post("/api/v1/postmortems/231/analysis",
                     json={"lang": "bn"}, headers=h)
    assert r1.json()["text"] == "EN analysis"
    assert r2.json()["text"] == "BN analysis"
    assert r2.json()["cached"] is False
    assert calls["n"] == 2
    assert r2.json()["used_today"] == 2
