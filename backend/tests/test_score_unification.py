"""Premium-apply batch — one score() for demo + landing + real app.

- services.recommend() returns the four factors (W/D/R/P) with every pick,
  and the score equals round(0.35W + 0.30D + 0.20R + 0.15P).
- Picks below MIN_SCORE_THRESHOLD (25) are dropped, in the real app and
  in the demo alike.
- seed.RECOMMENDATIONS (the demo list) uses the same production formula —
  no simplified mirror score — and its factors actually vary across picks.

Runs against a throwaway SQLite DB (TEST_DATABASE_URL). No network.
"""
import os
import sys
from datetime import datetime, timedelta

import pytest

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

from app import auth, models, seed, services  # noqa: E402
from app.db import Base  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    if os.path.exists("test_cpcompass.db"):
        os.remove("test_cpcompass.db")
    Base.metadata.create_all(bind=dbmod.engine)
    yield
    dbmod.engine.dispose()
    if os.path.exists("test_cpcompass.db"):
        os.remove("test_cpcompass.db")


@pytest.fixture()
def db():
    session = dbmod.SessionLocal()
    yield session
    session.close()


def _user(db, rating=1478):
    u = models.User(email="a@test.dev",
                    password_hash=auth.hash_password("secret123"),
                    current_rating=rating)
    db.add(u)
    db.commit()
    return u


def _prob(db, cid, idx, tags, rating=1300, name="P"):
    p = models.Problem(contest_id=cid, index=idx, name=name, rating=rating,
                       tags=tags, platform="codeforces")
    db.add(p)
    db.commit()
    return p


def _sub(db, user, prob, cf_id, verdict, day_offset=0):
    s = models.Submission(
        cf_submission_id=cf_id, user_id=user.id, problem_id=prob.id,
        verdict=verdict, language="C++17",
        submitted_at=datetime.utcnow() - timedelta(days=day_offset))
    db.add(s)
    db.commit()
    return s


def _weak_dp_history(db, user):
    """10 dp problems, 4 solved / 6 wrong, all recent: dp is weak
    (acceptance 0.40, weak_score ~0.56, attempted 10 >= 10)."""
    for i in range(10):
        p = _prob(db, 2000 + i, "A", ["dp"], rating=1300, name=f"DP{i}")
        _sub(db, user, p, 1000 + i, "OK" if i < 4 else "WRONG_ANSWER")


def _candidates():
    return [
        {"contestId": 1360, "index": "E", "name": "Polygon",
         "rating": 1500, "tags": ["dp", "graphs"]},
        {"contestId": 1366, "index": "C", "name": "Palindromic Paths",
         "rating": 1500, "tags": ["greedy", "math"]},
        # Below-band practice for a weak tag: in the widened band only.
        {"contestId": 4, "index": "A", "name": "Watermelon",
         "rating": 800, "tags": ["brute force", "math"]},
    ]


def test_threshold_constant_is_shared():
    assert services.MIN_SCORE_THRESHOLD == 25
    assert seed.MIN_SCORE_THRESHOLD == services.MIN_SCORE_THRESHOLD


def test_recommend_returns_factors_matching_formula(db):
    user = _user(db)
    _weak_dp_history(db, user)
    recs = services.recommend(db, user, _candidates(),
                              min_rating=800, max_rating=2000, limit=24)
    assert len(recs) == 2  # the 800-rated pick (score 19) is dropped
    for r in recs:
        f = r["factors"]
        assert set(f) == {"w", "d", "r", "p"}
        assert all(0 <= v <= 100 for v in f.values())
        assert r["score"] == round(
            0.35 * f["w"] + 0.30 * f["d"] + 0.20 * f["r"] + 0.15 * f["p"])
    assert [r["score"] for r in recs] == sorted(
        (r["score"] for r in recs), reverse=True)
    top = recs[0]
    assert (top["contest_id"], top["index"]) == (1360, "E")
    assert top["factors"]["w"] > 50  # dp is the weak tag
    assert top["factors"]["d"] == 61.0  # |1500 - 1578| * 0.5 off 100
    assert top["score"] == 59


def test_recommend_drops_below_threshold(db):
    user = _user(db)
    _weak_dp_history(db, user)
    recs = services.recommend(db, user, _candidates(),
                              min_rating=800, max_rating=2000, limit=24)
    ids = {(r["contest_id"], r["index"]) for r in recs}
    assert (4, "A") not in ids  # score 19 < 25
    assert (1366, "C") in ids  # score 37 >= 25


def test_demo_recommendations_use_production_formula():
    recs = seed.RECOMMENDATIONS
    assert len(recs) == 2  # only 1360E (43) and 1366C (37) survive
    assert [(r["contest_id"], r["index"]) for r in recs] == [
        (1360, "E"), (1366, "C")]
    for r in recs:
        f = r["factors"]
        assert r["score"] == round(
            0.35 * f["w"] + 0.30 * f["d"] + 0.20 * f["r"] + 0.15 * f["p"])
        assert r["score"] >= seed.MIN_SCORE_THRESHOLD
    by_id = {(r["contest_id"], r["index"]): r for r in recs}
    assert by_id[(1360, "E")]["score"] == 43
    assert by_id[(1360, "E")]["factors"] == {
        "w": 56.6, "d": 0.0, "r": 73.0, "p": 60.0}
    assert by_id[(1366, "C")]["score"] == 37
    assert by_id[(1366, "C")]["factors"] == {
        "w": 0.0, "d": 61.0, "r": 50.0, "p": 60.0}


def test_demo_factors_vary_across_candidates():
    """The factors are not decorative: W, D and R each take more than one
    value across the demo candidates. (P is constant 60 on the demo seed —
    no FAMOUS problem was attempted-but-unsolved; it varies on real
    accounts, where tried-but-unsolved problems score P=100.)"""
    recs = seed.RECOMMENDATIONS
    assert len({r["factors"]["w"] for r in recs}) > 1
    assert len({r["factors"]["d"] for r in recs}) > 1
    assert len({r["factors"]["r"] for r in recs}) > 1
