"""Batch 3 backtest tests (offline; no network is touched).

1. ml._metrics records log-loss (Batch 3 gap: it was never computed).
2. The by-time split is leakage-free: 157 train / 36 test rows at the
   2026-10-01 cutoff, test rows have prev_attempts 0, labels recomputed
   independently from the seed, and the pre-cutoff tag stats contain no
   post-cutoff problem.
3. The backtest's rule-score reimplementation agrees exactly with
   services.recommend() on a seeded test-DB user.
"""
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pytest

os.environ["TEST_DATABASE_URL"] = "sqlite:///./test_cpcompass.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "scripts"))

import app.config as config  # noqa: E402
config.DATABASE_URL = "sqlite:///./test_cpcompass.db"

import app.db as dbmod  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

dbmod.engine = create_engine(
    config.DATABASE_URL, connect_args={"check_same_thread": False})
dbmod.SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=dbmod.engine)

from app import auth, ml, models, services  # noqa: E402
from app.db import Base  # noqa: E402

import backtest  # noqa: E402


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


def test_metrics_includes_logloss():
    p = np.array([0.9, 0.1, 0.8, 0.2])
    y = np.array([1, 0, 1, 0])
    m = ml._metrics(p, y)
    # -(ln 0.9 + ln 0.9 + ln 0.8 + ln 0.8) / 4 = 0.164
    assert m["logloss"] == 0.164
    assert m["auc"] == 1.0
    assert m["brier"] == 0.025
    # Near-perfect predictions -> log-loss near zero.
    assert ml._metrics(np.array([0.99, 0.01]), np.array([1, 0]))["logloss"] < 0.05
    # Confidently wrong -> log-loss large.
    assert ml._metrics(np.array([0.01, 0.99]), np.array([1, 0]))["logloss"] > 4.0


def test_time_aware_split_counts_and_no_leakage():
    cutoff = datetime(2026, 10, 1)
    demo_subs, demo_hist, demo_rating = ml._demo_set()
    pre = [s for s in demo_subs if s["submitted_at"] < cutoff]
    top_tags = backtest._top_tags_for(pre)
    train, test, stats_pre, weak_pre = backtest.time_aware_rows(
        demo_subs, demo_hist, demo_rating, top_tags, cutoff)
    assert len(train) == 157
    assert len(test) == 36
    train_keys = {r["key"] for r in train}
    test_keys = {r["key"] for r in test}
    assert not train_keys & test_keys
    # Test rows: never attempted before the cutoff.
    assert all(r["features"]["prev_attempts"] == 0 for r in test)
    # Labels recomputed independently from the seed.
    first = {}
    for s in demo_subs:
        k = s["problem_key"]
        if k not in first or s["submitted_at"] < first[k]:
            first[k] = s["submitted_at"]
    for r in train:
        k = r["key"]
        expect = 1 if any(s["problem_key"] == k and s["verdict"] == "OK"
                          and s["submitted_at"] < cutoff
                          for s in demo_subs) else 0
        assert r["label"] == expect, k
        assert first[k] < cutoff
    for r in test:
        k = r["key"]
        expect = 1 if any(s["problem_key"] == k and s["verdict"] == "OK"
                          for s in demo_subs) else 0
        assert r["label"] == expect, k
        assert first[k] >= cutoff
    # The pre-cutoff tag stats contain no post-cutoff problem.
    for tag, st in stats_pre.items():
        for k in st["att_set"] | st["sol_set"]:
            assert first[k] < cutoff, (tag, k)


def _seed_user(db):
    """A user with 12 dp attempts (3 solved), 3 graphs, 2 math — dp is
    weak (12 attempts, acceptance 0.25). All submissions 5 days ago."""
    u = models.User(email="bt@test.dev",
                    password_hash=auth.hash_password("secret123"))
    db.add(u)
    db.commit()
    when = datetime.utcnow() - timedelta(days=5)
    plan = ([("dp", 1200 + 20 * i, "OK" if i < 3 else "WRONG_ANSWER")
             for i in range(12)]
            + [("graphs", 1250 + 50 * i, "OK" if i < 2 else "WRONG_ANSWER")
               for i in range(3)]
            + [("math", 1300 + 50 * i, "OK" if i == 0 else "TIME_LIMIT_EXCEEDED")
               for i in range(2)])
    for j, (tag, rating, verdict) in enumerate(plan):
        prob = models.Problem(contest_id=2000 + j, index="A",
                              name="Seed %d" % j, rating=rating, tags=[tag])
        db.add(prob)
        db.commit()
        db.add(models.Submission(user_id=u.id, problem_id=prob.id,
                                 cf_submission_id=900000 + j,
                                 verdict=verdict, submitted_at=when))
    db.commit()
    return u


def test_rule_score_matches_services_recommend(db):
    user = _seed_user(db)
    subs = ml._user_submission_dicts(db, user.id)
    stats = ml._tag_stats(subs)
    weak = {t: v for t, v in stats.items() if v["weak"]}
    assert "dp" in weak  # the weak path is exercised
    candidates = [
        {"contestId": 3001, "index": "A", "name": "Cand A", "rating": 1300,
         "tags": ["dp", "math"]},
        {"contestId": 3002, "index": "B", "name": "Cand B", "rating": 1250,
         "tags": ["graphs"]},
        {"contestId": 3003, "index": "C", "name": "Cand C", "rating": 1400,
         "tags": ["implementation"]},
    ]
    # current_rating is None -> recommend() uses 1200.
    got = services.recommend(db, user, candidates, limit=12)
    assert len(got) == 3
    by_key = {(c["contest_id"], c["index"]): c for c in got}
    for cand in candidates:
        key = (cand["contestId"], cand["index"])
        item = by_key[key]
        score, factors = backtest.rule_score(
            cand["tags"], cand["rating"], 1200, weak, attempted=False)
        assert item["score"] == score, key
        assert item["factors"] == factors, key
