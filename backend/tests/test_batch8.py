"""Batch 8 tests (NO SWITCH decision — by-time evaluation as an
informational artifact block, random split stays the ship gate).

1. ml.time_aware_rows is leakage-free (moved from backtest.py; the
   backtest keeps an alias to the same function).
2. The relative (80th-percentile) cutoff rule picks the right timestamp.
3. _time_aware_evaluation_for_sets runs on the demo data and records
   a usable split; it reports not-run (never raises) on tiny or
   single-class data.
4. train_model records evaluation["by_time"] in the artifact, and the
   ship decision still follows the RANDOM-split gate — not the
   by-time numbers. model_status serves the by_time block.
"""
import os
import sys
from datetime import datetime

os.environ["TEST_DATABASE_URL"] = "sqlite:///./test_cpcompass.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "scripts"))

import app.config as config  # noqa: E402
config.DATABASE_URL = "sqlite:///./test_cpcompass.db"

import backtest  # noqa: E402
from app import ml  # noqa: E402

CUTOFF = datetime(2026, 10, 1)


def _synthetic_subs():
    """Four problems across the 2026-10-01 cutoff, all tagged graphs.

    (1, A): first tried before the cutoff, solved ONLY after it — the
    leakage trap: its train label must be 0 and its post-cutoff OK
    must not enter the pre-cutoff tag stats.
    (1, B): solved before the cutoff — train label 1.
    (2, A/B): first tried after the cutoff — test rows, prev_attempts 0.
    """
    def sub(cid, idx, verdict, when, rating=1000):
        return {"problem_key": (cid, idx), "tags": ["graphs"],
                "verdict": verdict, "submitted_at": datetime.fromisoformat(when),
                "problem_rating": rating}
    return [
        sub(1, "A", "WRONG_ANSWER", "2026-08-01T10:00:00"),
        sub(1, "A", "OK", "2026-10-15T10:00:00"),
        sub(1, "B", "OK", "2026-08-05T10:00:00"),
        sub(2, "A", "WRONG_ANSWER", "2026-10-10T10:00:00"),
        sub(2, "B", "OK", "2026-11-01T10:00:00"),
    ]


def test_time_aware_rows_is_ml_function_and_backtest_alias():
    assert backtest.time_aware_rows is ml.time_aware_rows


def test_time_aware_rows_leakage_free():
    subs = _synthetic_subs()
    hist = [(datetime(2026, 1, 1), 1200)]
    train, test, stats_pre, _weak = ml.time_aware_rows(
        subs, hist, 1200, ["graphs"], CUTOFF)
    train_by_key = {r["key"]: r for r in train}
    test_by_key = {r["key"]: r for r in test}
    assert set(train_by_key) == {(1, "A"), (1, "B")}
    assert set(test_by_key) == {(2, "A"), (2, "B")}
    # The post-cutoff-only solve must not leak into the train label.
    assert train_by_key[(1, "A")]["label"] == 0
    assert train_by_key[(1, "B")]["label"] == 1
    assert test_by_key[(2, "A")]["label"] == 0
    assert test_by_key[(2, "B")]["label"] == 1
    # Test rows are first attempts: no attempts before the cutoff.
    assert all(r["features"]["prev_attempts"] == 0 for r in test)
    # Pre-cutoff tag stats contain no post-cutoff problem.
    assert (2, "A") not in stats_pre["graphs"]["att_set"]
    assert (2, "B") not in stats_pre["graphs"]["att_set"]
    # Tag acceptance for a test row: pre-cutoff graphs = (1, A) unsolved
    # + (1, B) solved -> 1/2. The post-cutoff OK on (1, A) must not
    # count (leaked stats would give 2/2 = 1.0).
    assert test_by_key[(2, "A")]["features"]["min_tag_acc"] == 0.5
    assert test_by_key[(2, "A")]["features"]["mean_tag_acc"] == 0.5


def test_relative_cutoff_rule():
    firsts = [datetime(2026, 1, d) for d in range(1, 11)]
    # 80th percentile of 10 timestamps -> index 8 (the 9th).
    assert ml._relative_cutoff(firsts) == datetime(2026, 1, 9)
    assert ml._relative_cutoff(firsts, quantile=0.5) == datetime(2026, 1, 6)


def test_time_aware_evaluation_runs_on_demo():
    sets = ml._data_sets(None)
    out = ml._time_aware_evaluation_for_sets(sets)
    assert out["ran"] is True
    assert out["cutoff_rule"].startswith("80th percentile")
    assert 30 <= out["split"]["test"] <= 50
    assert out["split"]["train"] >= 100
    assert 0 < out["split"]["test_solved"] < out["split"]["test"]
    assert out["test_composition"] == {"demo_coder (seed)": out["split"]["test"]}
    assert 0.5 < out["random_forest"]["test_auc"] < 0.95
    assert "logreg" in out and "baseline" in out


def test_time_aware_evaluation_not_run_when_too_small():
    def sub(cid, idx, verdict, when):
        return {"problem_key": (cid, idx), "tags": ["graphs"],
                "verdict": verdict, "submitted_at": datetime.fromisoformat(when),
                "problem_rating": 1000}
    tiny = [sub(1, "A", "OK", "2026-08-01T10:00:00"),
            sub(1, "B", "WRONG_ANSWER", "2026-08-02T10:00:00")]
    out = ml._time_aware_evaluation_for_sets(
        [(tiny, [], 1200, "tiny")])
    assert out["ran"] is False
    assert "not enough rows" in out["reason"]


def test_time_aware_evaluation_not_run_when_single_class():
    def sub(cid, idx, when):
        return {"problem_key": (cid, idx), "tags": ["graphs"],
                "verdict": "OK", "submitted_at": datetime.fromisoformat(when),
                "problem_rating": 1000}
    # 100 solved problems spread over 2026: the test slice (newest ~20%,
    # Sep-Oct) is >= 20 rows and all solved -> single-class, not too-small.
    subs = [sub(100 + i, "A", f"2026-{m:02d}-10T10:00:00")
            for i, m in enumerate([1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 10)]
    out = ml._time_aware_evaluation_for_sets(
        [(subs, [(datetime(2026, 1, 1), 1200)], 1200, "all-solved")])
    assert out["ran"] is False
    assert "single-class" in out["reason"]


def test_train_model_records_by_time_and_ship_rule_stays_random(tmp_path, monkeypatch):
    monkeypatch.setattr(ml, "MODEL_PATH", str(tmp_path / "model.joblib"))
    try:
        report = ml.train_model(None)
    finally:
        ml._model_cache["mtime"] = None
        ml._model_cache["artifact"] = None
    assert report["trained"] is True
    ev = report["evaluation"]
    assert ev["by_time"]["ran"] is True
    assert ev["by_time"]["split"]["test"] >= 20
    # The ship decision follows the RANDOM-split gate, not by-time:
    # recompute the gate from the random numbers and compare.
    rf = ev["random_forest"]
    base = ev["baseline"]
    expect_shipped = (rf["test_auc"] is not None and base["auc"] is not None
                      and rf["test_auc"] > base["auc"]
                      and rf["test_brier"] < base["brier"])
    assert report["shipped"] is expect_shipped
    assert report["shipped"] is True  # demo data still ships on random


def test_model_status_serves_by_time(tmp_path, monkeypatch):
    monkeypatch.setattr(ml, "MODEL_PATH", str(tmp_path / "model.joblib"))
    try:
        ml.train_model(None)
        status = ml.model_status(None)
    finally:
        ml._model_cache["mtime"] = None
        ml._model_cache["artifact"] = None
    assert status["trained"] is True
    assert status["evaluation"]["by_time"]["ran"] is True
    assert "cutoff" in status["evaluation"]["by_time"]
