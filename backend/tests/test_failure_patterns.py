"""Batch 2 — failure-pattern analysis.

- Sync stores passedTestCount on new submissions; the backfill fills
  rows synced before the column existed.
- failure_patterns: verdict breakdown, early/middle/late test stages
  (NULL counts land in `unknown`), per-topic signal thresholds, thin
  data flags, wrong-before-first-AC buckets.
- problem_detail carries passed_test_count; the /analytics/failures
  endpoint serves the same payload.

Runs against a throwaway SQLite DB (TEST_DATABASE_URL). CF calls are
monkeypatched — no network is touched.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta

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

from app import auth, models, services, sync as sync_engine  # noqa: E402
from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    if os.path.exists("test_cpcompass.db"):
        os.remove("test_cpcompass.db")
    Base.metadata.create_all(bind=dbmod.engine)
    yield
    dbmod.engine.dispose()
    if os.path.exists("test_cpcompass.db"):
        os.remove("test_cpcompass.db")


def _user(db, email="a@test.dev"):
    u = models.User(email=email, password_hash=auth.hash_password("secret123"))
    db.add(u)
    db.commit()
    return u


def _auth_headers(user_id):
    session = dbmod.SessionLocal()
    try:
        tokens = auth.issue_tokens(session, user_id)
    finally:
        session.close()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def db():
    session = dbmod.SessionLocal()
    yield session
    session.close()


def _prob(db, cid, idx, tags, rating=1000, name="P"):
    p = models.Problem(contest_id=cid, index=idx, name=name, rating=rating,
                       tags=tags, platform="codeforces")
    db.add(p)
    db.commit()
    return p


def _sub(db, user, prob, cf_id, verdict, passed, day_offset=0):
    s = models.Submission(
        cf_submission_id=cf_id, user_id=user.id, problem_id=prob.id,
        verdict=verdict, language="C++17",
        submitted_at=datetime.utcnow() - timedelta(days=day_offset),
        passed_test_count=passed)
    db.add(s)
    db.commit()
    return s


def _cf_sub(cf_id, verdict, passed, cid=1730, idx="A"):
    return {"id": cf_id, "verdict": verdict, "creationTimeSeconds": 1700000000,
            "programmingLanguage": "C++17", "passedTestCount": passed,
            "problem": {"contestId": cid, "index": idx, "name": "P",
                        "rating": 1000, "tags": ["dp"]}}


def test_sync_stores_passed_test_count(client, db, monkeypatch):
    """A synced submission keeps its passedTestCount."""
    user = _user(db)
    db.add(models.CfAccount(user_id=user.id, handle="tourist",
                            handle_norm="tourist"))
    db.commit()

    async def fake_status(handle, start_from=1, count=1000):
        return [_cf_sub(111, "WRONG_ANSWER", 2)] if start_from == 1 else []

    async def fake_rating(handle):
        return []
    monkeypatch.setattr(sync_engine.cf, "user_status", fake_status)
    monkeypatch.setattr(sync_engine.cf, "user_rating", fake_rating)

    job = sync_engine.enqueue_sync(db, user.id)
    asyncio.run(sync_engine.run_sync(db, user, job))
    row = db.query(models.Submission).first()
    assert row is not None
    assert row.passed_test_count == 2
    assert row.verdict == "WRONG_ANSWER"


def test_backfill_fills_null_counts(db, monkeypatch):
    """Rows synced before Batch 2 get their test counts from a re-fetch."""
    user = _user(db)
    db.add(models.CfAccount(user_id=user.id, handle="tourist",
                            handle_norm="tourist"))
    db.commit()
    prob = _prob(db, 1730, "A", ["dp"])
    _sub(db, user, prob, 111, "WRONG_ANSWER", None)
    _sub(db, user, prob, 112, "OK", None)

    async def fake_status(handle, start_from=1, count=1000):
        return [_cf_sub(111, "WRONG_ANSWER", 1),
                _cf_sub(112, "OK", 12)] if start_from == 1 else []
    monkeypatch.setattr(sync_engine.cf, "user_status", fake_status)

    filled = asyncio.run(sync_engine.backfill_passed_test_counts(db, user))
    assert filled == 2
    rows = {r.cf_submission_id: r.passed_test_count
            for r in db.query(models.Submission).all()}
    assert rows == {111: 1, 112: 12}
    # Second run: nothing left to fill, no CF calls needed.
    filled_again = asyncio.run(sync_engine.backfill_passed_test_counts(db, user))
    assert filled_again == 0


def test_verdict_breakdown_and_stages(db):
    """Breakdown counts every verdict; stages bucket known counts and
    put NULL counts in `unknown`."""
    user = _user(db)
    p = _prob(db, 1730, "A", ["dp"])
    _sub(db, user, p, 1, "OK", 10)
    _sub(db, user, p, 2, "WRONG_ANSWER", 1)
    _sub(db, user, p, 3, "WRONG_ANSWER", 2)
    _sub(db, user, p, 4, "WRONG_ANSWER", 5)
    _sub(db, user, p, 5, "TIME_LIMIT_EXCEEDED", 15)
    _sub(db, user, p, 6, "RUNTIME_ERROR", None)

    out = services.failure_patterns(db, user.id)
    assert out["total_submissions"] == 6
    assert out["total_wrong"] == 5
    assert out["with_test_data"] == 5
    assert out["without_test_data"] == 1
    assert out["enough_data"] is True
    assert {b["verdict"]: b["count"] for b in out["verdict_breakdown"]} == {
        "OK": 1, "WRONG_ANSWER": 3, "TIME_LIMIT_EXCEEDED": 1, "RUNTIME_ERROR": 1}
    assert out["test_stages"] == {"early": 2, "middle": 1, "late": 1, "unknown": 1}


def test_per_topic_signal_thresholds(db):
    """3+ wrongs with >= 60% early -> 'early'; fewer than 3 wrongs ->
    'thin' (counts shown, no pattern claimed); neither stage
    dominating -> 'mixed'."""
    user = _user(db)
    graphs = _prob(db, 20, "C", ["graphs"], rating=1400, name="G")
    dp = _prob(db, 1741, "C", ["dp"], rating=1100, name="D")
    greedy = _prob(db, 50, "A", ["greedy"], rating=800, name="Gr")
    # graphs: 3 wrongs, all early.
    _sub(db, user, graphs, 1, "WRONG_ANSWER", 0, day_offset=5)
    _sub(db, user, graphs, 2, "WRONG_ANSWER", 1, day_offset=4)
    _sub(db, user, graphs, 3, "WRONG_ANSWER", 2, day_offset=3)
    # dp: 2 wrongs only -> thin even though both early.
    _sub(db, user, dp, 4, "WRONG_ANSWER", 1, day_offset=5)
    _sub(db, user, dp, 5, "WRONG_ANSWER", 0, day_offset=4)
    # greedy: 4 wrongs spread across stages -> mixed.
    _sub(db, user, greedy, 6, "WRONG_ANSWER", 1, day_offset=5)
    _sub(db, user, greedy, 7, "WRONG_ANSWER", 5, day_offset=4)
    _sub(db, user, greedy, 8, "WRONG_ANSWER", 12, day_offset=3)
    _sub(db, user, greedy, 9, "TIME_LIMIT_EXCEEDED", 20, day_offset=2)

    out = services.failure_patterns(db, user.id)
    by_tag = {t["tag"]: t for t in out["per_topic"]}
    assert by_tag["graphs"]["signal"] == "early"
    assert by_tag["graphs"]["wrong"] == 3
    assert by_tag["graphs"]["early_share"] == 1.0
    assert by_tag["graphs"]["median_passed"] == 1.0
    assert by_tag["dp"]["signal"] == "thin"
    assert by_tag["greedy"]["signal"] == "mixed"


def test_no_test_data_means_thin(db):
    """Wrong submissions without any test counts claim no pattern —
    'mixed' would imply we know the stages are spread, and we don't."""
    user = _user(db)
    prob = _prob(db, 4, "A", ["brute force"], rating=800, name="W")
    _sub(db, user, prob, 1, "WRONG_ANSWER", None, day_offset=5)
    _sub(db, user, prob, 2, "WRONG_ANSWER", None, day_offset=4)
    _sub(db, user, prob, 3, "WRONG_ANSWER", None, day_offset=3)
    _sub(db, user, prob, 4, "WRONG_ANSWER", None, day_offset=2)
    out = services.failure_patterns(db, user.id)
    assert out["total_wrong"] == 4
    assert out["test_stages"] == {"early": 0, "middle": 0, "late": 0, "unknown": 4}
    assert out["per_topic"][0]["tag"] == "brute force"
    assert out["per_topic"][0]["signal"] == "thin"


def test_wrong_before_first_ac_and_per_problem(db):
    """Per-problem list ranks by wrong attempts; AC buckets count wrong
    submissions strictly before the first OK."""
    user = _user(db)
    hard = _prob(db, 4, "A", ["brute force"], rating=800, name="W")
    easy = _prob(db, 71, "A", ["strings"], rating=800, name="T")
    unsolved = _prob(db, 20, "C", ["graphs"], rating=1400, name="D")
    # hard: 3 wrongs (days 5,4,3) then OK (day 2), then 1 more wrong (day 1).
    _sub(db, user, hard, 1, "WRONG_ANSWER", 1, day_offset=5)
    _sub(db, user, hard, 2, "WRONG_ANSWER", 2, day_offset=4)
    _sub(db, user, hard, 3, "WRONG_ANSWER", 0, day_offset=3)
    _sub(db, user, hard, 4, "OK", 8, day_offset=2)
    _sub(db, user, hard, 5, "WRONG_ANSWER", 3, day_offset=1)
    # easy: OK first try.
    _sub(db, user, easy, 6, "OK", 6, day_offset=2)
    # unsolved: 1 wrong, never solved.
    _sub(db, user, unsolved, 7, "WRONG_ANSWER", 4, day_offset=2)

    out = services.failure_patterns(db, user.id)
    assert out["per_problem"][0]["problem"]["index"] == "A"
    assert out["per_problem"][0]["wrong_attempts"] == 4
    assert out["per_problem"][0]["solved"] is True
    assert out["per_problem"][0]["passed_tests"] == [0, 1, 2, 3]
    assert out["wrong_before_first_ac"]["zero"] == 1      # easy
    assert out["wrong_before_first_ac"]["three_plus"] == 1  # hard (3 before AC)
    assert out["wrong_before_first_ac"]["one_two"] == 0
    assert out["wrong_before_first_ac"]["median"] == 1.5
    assert out["wrong_before_first_ac"]["solved_problems"] == 2


def test_thin_data_flags(db):
    """No submissions at all: everything zero, enough_data False, no crash."""
    user = _user(db)
    out = services.failure_patterns(db, user.id)
    assert out["total_submissions"] == 0
    assert out["total_wrong"] == 0
    assert out["enough_data"] is False
    assert out["verdict_breakdown"] == []
    assert out["test_stages"] == {"early": 0, "middle": 0, "late": 0, "unknown": 0}
    assert out["per_topic"] == []
    assert out["per_problem"] == []


def test_problem_detail_carries_test_count(db):
    """The detail page's submission rows include passed_test_count."""
    user = _user(db)
    prob = _prob(db, 1730, "A", ["dp"])
    _sub(db, user, prob, 1, "WRONG_ANSWER", 2, day_offset=2)
    _sub(db, user, prob, 2, "OK", 9, day_offset=1)
    detail = services.problem_detail(db, user.id, 1730, "A")
    assert detail is not None
    assert [s["passed_test_count"] for s in detail["submissions"]] == [9, 2]


def test_failures_endpoint(client, db):
    """GET /api/v1/analytics/failures serves the analysis for the caller."""
    user = _user(db)
    db.add(models.CfAccount(user_id=user.id, handle="tourist",
                            handle_norm="tourist"))
    db.commit()
    prob = _prob(db, 1730, "A", ["dp"])
    _sub(db, user, prob, 1, "OK", 10)
    _sub(db, user, prob, 2, "WRONG_ANSWER", 1)
    resp = client.get("/api/v1/analytics/failures",
                      headers=_auth_headers(user.id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_submissions"] == 2
    assert body["total_wrong"] == 1
    assert body["test_stages"]["early"] == 1
    # No handle connected -> 400, not a leak.
    user2 = _user(db, email="b@test.dev")
    resp2 = client.get("/api/v1/analytics/failures",
                       headers=_auth_headers(user2.id))
    assert resp2.status_code == 400
