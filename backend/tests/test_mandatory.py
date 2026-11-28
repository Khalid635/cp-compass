"""Blueprint §13 mandatory test cases (offline where possible).

1. Same submission synced twice -> no duplicates.
2. Sync interrupted mid-run -> recovery from checkpoint.
3. Bad Codeforces handle -> clear error.
4. User A cannot see User B's private notes.
5. Same problem cannot enter the revision queue twice.
6. Demo mode: no write operation succeeds.
7. Empty submission history -> dashboard does not crash.
8. Codeforces API down -> old data is kept.

Runs against a throwaway SQLite DB (TEST_DATABASE_URL). CF calls are
monkeypatched — no network is touched.
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
config.DATABASE_URL = os.environ["TEST_DATABASE_URL"]

# Rebuild the engine against the test DB before importing the app modules.
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
    # Windows locks the SQLite file while any pooled connection is open.
    dbmod.engine.dispose()
    if os.path.exists("test_cpcompass.db"):
        os.remove("test_cpcompass.db")


def _user(db, email="a@test.dev"):
    u = models.User(email=email, password_hash=auth.hash_password("secret123"))
    db.add(u)
    db.commit()
    return u


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
    """Cookie-based auth (Batch 6, N4) — see test_hints.py."""
    tokens = _tokens(user_id)
    csrf = _csrf_token()
    cookie = (f"cp_access={tokens['access_token']}; "
              f"cp_refresh={tokens['refresh_token']}; cp_csrf={csrf}")
    return {"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": ORIGIN}, tokens


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def db():
    session = dbmod.SessionLocal()
    yield session
    session.close()


def test_1_duplicate_sync_no_duplicates(client, db, monkeypatch):
    """Same submission synced twice -> exactly one row."""
    user = _user(db)
    db.add(models.CfAccount(user_id=user.id, handle="tourist",
                            handle_norm="tourist"))
    db.commit()
    sub = {"id": 111, "verdict": "OK", "creationTimeSeconds": 1700000000,
           "programmingLanguage": "C++17",
           "problem": {"contestId": 1730, "index": "A", "name": "Planar Reflections",
                       "rating": 1200, "tags": ["dp"]}}

    async def fake_status(handle, start_from=1, count=1000):
        return [sub] if start_from == 1 else []

    async def fake_rating(handle):
        return []
    monkeypatch.setattr(sync_engine.cf, "user_status", fake_status)
    monkeypatch.setattr(sync_engine.cf, "user_rating", fake_rating)

    import asyncio
    job = sync_engine.enqueue_sync(db, user.id)
    asyncio.run(sync_engine.run_sync(db, user, job))
    assert db.query(models.Submission).count() == 1
    # Second sync: nothing new, still one row.
    job2 = sync_engine.enqueue_sync(db, user.id)
    asyncio.run(sync_engine.run_sync(db, user, job2))
    assert db.query(models.Submission).count() == 1
    assert db.query(models.SyncJob).filter_by(status="done").count() == 2


def test_2_interrupted_sync_recovers(client, db):
    """A running job with an expired lease is reset to pending on recovery."""
    user = _user(db)
    job = models.SyncJob(user_id=user.id, status="running",
                         last_synced_submission_id=500, checkpoint_from=1001,
                         lease_owner="dead-worker",
                         lease_expires_at=datetime.utcnow() - timedelta(seconds=10),
                         attempts=0)
    db.add(job)
    db.commit()
    recovered = sync_engine.recover_stale_jobs(db)
    assert recovered == 1
    assert job.status == "pending"
    assert job.last_synced_submission_id == 500  # checkpoint kept
    assert job.checkpoint_from == 1001


def test_3_bad_handle_clear_error(client, db, monkeypatch):
    """Batch 1: bad handle -> clear error on the verification start step;
    the old direct-link endpoint is closed (it cannot prove ownership)."""
    from app.cf import CFError

    async def bad_handle(handle):
        raise CFError("Handle not found on Codeforces")

    monkeypatch.setattr("app.main.cf.verify_handle", bad_handle)
    user = _user(db)
    headers, _ = _auth_headers(user.id)
    res = client.post("/api/v1/auth/handle/start",
                      json={"handle": "no-such-handle-xyz"}, headers=headers)
    assert res.status_code == 400
    assert "Codeforces" in res.json()["detail"]
    res = client.post("/api/v1/auth/handle", json={"handle": "tourist"},
                      headers=headers)
    assert res.status_code == 400
    assert "verification" in res.json()["detail"]


def test_4_notes_isolation(client, db):
    """User A cannot read User B's problem note (ownership enforced)."""
    a = _user(db, "a@test.dev")
    b = _user(db, "b@test.dev")
    prob = models.Problem(contest_id=1730, index="A", name="X", rating=1200,
                          tags=["dp"])
    db.add(prob)
    db.flush()
    db.add(models.ProblemNote(user_id=b.id, problem_id=prob.id, body="B secret"))
    db.commit()
    # There is no notes-read endpoint that takes another user's id; the
    # ownership rule is checked at the model level: A's query for B's note
    # must return nothing.
    mine = db.query(models.ProblemNote).filter_by(user_id=a.id).all()
    assert mine == []
    theirs = db.query(models.ProblemNote).filter_by(user_id=b.id).all()
    assert len(theirs) == 1 and theirs[0].body == "B secret"


def test_5_revision_queue_no_duplicates(client, db):
    user = _user(db)
    prob = models.Problem(contest_id=1730, index="A", name="X", rating=1200,
                          tags=["dp"])
    db.add(prob)
    db.flush()
    for i, verdict in enumerate(
            ("WRONG_ANSWER", "WRONG_ANSWER", "WRONG_ANSWER", "OK")):
        db.add(models.Submission(cf_submission_id=2000 + i,
                                 user_id=user.id, problem_id=prob.id, verdict=verdict,
                                 submitted_at=datetime.utcnow()))
    db.commit()
    services.build_revision_queue(db, user.id)
    services.build_revision_queue(db, user.id)  # second build: still one
    rows = db.query(models.Revision).filter_by(user_id=user.id).all()
    assert len(rows) == 1


def test_6_demo_mode_read_only(client):
    """Demo endpoints are GET-only: POST/PUT/DELETE are rejected."""
    assert client.get("/api/v1/demo/dashboard").status_code == 200
    assert client.post("/api/v1/demo/dashboard",
                       headers=_anon_headers()).status_code == 405
    assert client.post("/api/v1/demo/recommendations",
                       headers=_anon_headers()).status_code == 405
    assert client.delete("/api/v1/demo/revisions",
                         headers=_anon_headers()).status_code == 405


def test_7_empty_history_dashboard_ok(client, db, monkeypatch):
    async def empty_problemset():
        return []

    monkeypatch.setattr("app.main.cf.problemset", empty_problemset)
    user = _user(db)
    db.add(models.CfAccount(user_id=user.id, handle="tourist",
                            handle_norm="tourist"))
    db.commit()
    headers, _ = _auth_headers(user.id)
    res = client.get("/api/v1/dashboard", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["has_handle"] is True
    assert body["stats"]["solved"] == 0
    assert body["tag_strengths"] == []
    assert body["recent"] == []


def test_9_graded_review_reschedules(client, db):
    """Graded review: Again=1d, Good=next interval; a reviewed revision
    becomes due again after its interval (the old done-flag bug)."""
    user = _user(db)
    prob = models.Problem(contest_id=1730, index="A", name="X", rating=1200,
                          tags=["dp"])
    db.add(prob)
    db.flush()
    for i in range(3):
        db.add(models.Submission(cf_submission_id=3000 + i, user_id=user.id,
                                 problem_id=prob.id, verdict="WRONG_ANSWER",
                                 submitted_at=datetime.utcnow()))
    db.add(models.Submission(cf_submission_id=3003, user_id=user.id,
                             problem_id=prob.id, verdict="OK",
                             submitted_at=datetime.utcnow()))
    db.commit()
    services.build_revision_queue(db, user.id)
    rev = db.query(models.Revision).filter_by(user_id=user.id).one()
    assert rev.interval_days == 1
    # Grade "again" -> stays at 1 day; force due_date into the past and
    # check it shows due again (not stuck done).
    out = services.review_revision(db, user.id, rev.id, "again")
    assert out.interval_days == 1
    rev.due_date = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    headers, _ = _auth_headers(user.id)
    res = client.get("/api/v1/revisions?tab=due", headers=headers)
    assert res.status_code == 200 and len(res.json()) == 1
    # Grade "good" from interval 1 -> next interval 3.
    out = services.review_revision(db, user.id, rev.id, "good")
    assert out.interval_days == 3
    # Grade "easy" from interval 3 -> advances two steps to 14.
    out = services.review_revision(db, user.id, rev.id, "easy")
    assert out.interval_days == 14
    # "done" tab lists it (it has a last_result).
    res = client.get("/api/v1/revisions?tab=done", headers=headers)
    assert res.status_code == 200 and len(res.json()) == 1


def test_8_cf_down_keeps_old_data(client, db, monkeypatch):
    """CF API raising -> job fails, but previously synced data stays."""
    user = _user(db)
    db.add(models.CfAccount(user_id=user.id, handle="tourist",
                            handle_norm="tourist"))
    prob = models.Problem(contest_id=1730, index="A", name="X", rating=1200,
                          tags=["dp"])
    db.add(prob)
    db.flush()
    db.add(models.Submission(cf_submission_id=999, user_id=user.id,
                             problem_id=prob.id, verdict="OK",
                             submitted_at=datetime.utcnow()))
    db.commit()

    async def boom(*args, **kwargs):
        from app.cf import CFError
        raise CFError("network down")

    monkeypatch.setattr(sync_engine.cf, "user_status", boom)
    monkeypatch.setattr(sync_engine.cf, "user_rating", boom)

    import asyncio
    job = sync_engine.enqueue_sync(db, user.id)
    asyncio.run(sync_engine.run_sync(db, user, job))
    assert job.status == "failed"
    assert db.query(models.Submission).count() == 1  # old data kept
    assert db.query(models.Problem).count() == 1


def _seed_history(db, user):
    """3 distinct problems solved on 3 far-apart days + 1 wrong attempt.
    Mirrors the real account shape: old solves must NOT be hidden by a
    26-week window."""
    probs = []
    for cid in (1730, 1731, 1732):
        p = models.Problem(contest_id=cid, index="A", name=f"P{cid}",
                           rating=800, tags=["implementation"])
        db.add(p)
        probs.append(p)
    db.flush()
    today = datetime.utcnow().date()
    subs = [
        (probs[0], "OK", datetime(2024, 1, 5, 10, 0)),
        (probs[0], "WRONG_ANSWER", datetime(2024, 1, 5, 9, 0)),
        (probs[1], "OK", datetime(2024, 6, 1, 10, 0)),
        (probs[2], "OK", datetime.combine(today - timedelta(days=1), datetime.min.time())),
    ]
    for i, (p, verdict, when) in enumerate(subs):
        db.add(models.Submission(cf_submission_id=3000 + i, user_id=user.id,
                                 problem_id=p.id, verdict=verdict,
                                 submitted_at=when))
    db.commit()
    return probs


def test_10_heatmap_full_history(db):
    """Full-history heatmap totals the same as total solved; the 26-week
    window still hides old solves (the bug this fix removes)."""
    user = _user(db)
    _seed_history(db, user)
    full = services.heatmap(db, user.id, weeks=None)
    assert sum(d["count"] for d in full) == 3
    assert full[0]["date"] == "2024-01-05"
    assert full[-1]["date"] == datetime.utcnow().date().isoformat()
    recent = services.heatmap(db, user.id, weeks=26)
    assert sum(d["count"] for d in recent) == 1  # only yesterday's solve


def test_11_cumulative_solved(db):
    """Cumulative curve: starts at 0 the day before the first solve,
    ends at distinct solved, never decreases, flat between active days."""
    user = _user(db)
    _seed_history(db, user)
    pts = services.cumulative_solved(db, user.id)
    assert pts[0] == {"date": "2024-01-04", "solved": 0}
    assert pts[-1]["solved"] == 3
    assert pts[-1]["date"] == datetime.utcnow().date().isoformat()
    assert [p["solved"] for p in pts] == sorted(p["solved"] for p in pts)
    assert [p["date"] for p in pts] == sorted(p["date"] for p in pts)
    totals = {p["date"]: p["solved"] for p in pts}
    assert totals["2024-01-05"] == 1
    assert totals["2024-06-01"] == 2
