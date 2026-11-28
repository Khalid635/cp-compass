"""Batch 8 split sensitivity (measurement only — no training changes).

Answers, with numbers, whether the shipped random 80/20 training split
should move to a by-time split:

1. Random-split seed sensitivity: protocol A (combined demo + real rows)
   across seeds [42, 1, 7, 123, 2026]. Is the shipped 0.773 a lucky seed?
2. By-time cutoff sensitivity (demo-only, protocol B method): cutoffs
   2026-09-01 / 09-15 / 10-01 / 10-15 / 11-01. Is the 0.683 at 10-01
   stable, and does logreg keep beating RF forward?
3. Combined-dataset by-time at the primary cutoff 2026-10-01: the
   shipped path's actual evaluation (demo + real rows, per-user
   pre-cutoff tag stats, leakage-free — mirrors backtest.time_aware_rows
   generalized to multiple user sets).
4. Combined-dataset by-time at the RELATIVE cutoff (80th percentile of
   first-attempt times, newest ~20% as test): the cutoff rule the switch
   would actually ship, since a fixed date rots.

Run from the backend dir with the venv:
    python scripts/split_sensitivity.py
Writes specs/batch8/sensitivity-results.json and prints a summary.
Read-only on the dev DB (SQLite); no model is trained for shipping.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import ml  # noqa: E402
from app.db import SessionLocal  # noqa: E402
import backtest as bt  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.normpath(os.path.join(
    _HERE, "..", "..", "specs", "batch8", "sensitivity-results.json"))

RANDOM_SEEDS = [42, 1, 7, 123, 2026]
CUTOFFS = ["2026-09-01", "2026-09-15", "2026-10-01", "2026-10-15",
           "2026-11-01"]
PRIMARY_CUTOFF = "2026-10-01"


def _model_summary(results):
    """test AUC/Brier/log-loss (+CV AUC) per candidate, backtest shape."""
    return {k: {"cv_auc": v["cv_auc"], "test_auc": v["test_auc"],
                "test_brier": v["test_brier"],
                "test_logloss": v["test_logloss"]}
            for k, v in results.items()}


def random_seed_run(db, seed):
    """Protocol A with a different random_state (combined rows)."""
    rows, top_tags, sources = ml.collect_rows(db)
    feature_names = ml._feature_names(top_tags)
    X, y, base = ml._rows_to_xy(rows, feature_names)
    try:
        X_tr, X_te, y_tr, y_te, b_tr, b_te = train_test_split(
            X, y, base, test_size=0.2, random_state=seed, stratify=y)
    except ValueError:
        X_tr, X_te, y_tr, y_te, b_tr, b_te = train_test_split(
            X, y, base, test_size=0.2, random_state=seed)
    elo_te = np.array([bt.elo_prob(int(r), int(p))
                       for r, p in zip(X_te[:, 0], X_te[:, 1])])
    out = {"seed": seed, "n_train": int(len(y_tr)), "n_test": int(len(y_te)),
           "test_solved": int(y_te.sum()),
           "test_unsolved": int(len(y_te) - y_te.sum()),
           "baseline_rule": ml._metrics(b_te, y_te),
           "baseline_elo": ml._metrics(elo_te, y_te)}
    results, _, _ = bt._eval_candidates(X_tr, y_tr, X_te, y_te)
    out.update(_model_summary(results))
    return out


def _all_sets(db):
    """[(subs, hist, current_rating, name)] for demo + each DB user."""
    demo_subs, demo_hist, demo_rating = ml._demo_set()
    sets = [(demo_subs, demo_hist, demo_rating, "demo_coder (seed)")]
    if db is not None:
        sets.extend(ml._db_sets(db))
    return sets


def combined_by_time(db, cutoff):
    """Leakage-free by-time split over the COMBINED dataset.

    Top tags come from pre-cutoff submissions across all users; each
    user's rows use that user's own pre-cutoff tag stats (same method
    as backtest.time_aware_rows, per user). Returns metrics + the test
    set's composition (demo vs real rows) so a tiny real contribution
    cannot hide inside the headline number.
    """
    sets = _all_sets(db)
    pre_subs = [s for subs, _, _, _ in sets for s in subs
                if s["submitted_at"] < cutoff]
    top_tags = bt._top_tags_for(pre_subs)
    train_rows, test_rows = [], []
    for subs, hist, rating, name in sets:
        tr, te, _, _ = bt.time_aware_rows(subs, hist, rating, top_tags,
                                          cutoff)
        for r in tr:
            r["source"] = name
        for r in te:
            r["source"] = name
        train_rows.extend(tr)
        test_rows.extend(te)
    feature_names = ml._feature_names(top_tags)
    X_tr, y_tr, b_tr = ml._rows_to_xy(train_rows, feature_names)
    X_te, y_te, b_te = ml._rows_to_xy(test_rows, feature_names)
    elo_te = np.array([bt.elo_prob(int(r), int(p))
                       for r, p in zip(X_te[:, 0], X_te[:, 1])])
    comp = defaultdict(int)
    for r in test_rows:
        comp[r["source"]] += 1
    out = {"cutoff": cutoff.isoformat(),
           "n_train": len(train_rows), "n_test": len(test_rows),
           "train_solved": int(y_tr.sum()),
           "test_solved": int(y_te.sum()),
           "test_composition": dict(comp),
           "top_tags": top_tags,
           "baseline_rule": ml._metrics(b_te, y_te),
           "baseline_elo": ml._metrics(elo_te, y_te)}
    results, _, _ = bt._eval_candidates(X_tr, y_tr, X_te, y_te)
    out.update(_model_summary(results))
    return out


def relative_cutoff(db, quantile=0.8):
    """First-attempt timestamp at the quantile of all rows' first
    attempts (newest ~20% as test). A fixed date rots; this adapts."""
    firsts = []
    for subs, _, _, _ in _all_sets(db):
        by_prob = defaultdict(list)
        for s in subs:
            by_prob[s["problem_key"]].append(s)
        firsts.extend(min(s["submitted_at"] for s in ss)
                      for ss in by_prob.values())
    firsts.sort()
    return firsts[min(int(quantile * len(firsts)), len(firsts) - 1)]


def real_rows_first_attempts(db):
    """First-attempt date per real (DB) problem — for interpreting the
    combined by-time test set."""
    out = []
    for subs, _, _, name in _all_sets(db):
        if name == "demo_coder (seed)":
            continue
        by_prob = defaultdict(list)
        for s in subs:
            by_prob[s["problem_key"]].append(s)
        for key, ss in sorted(by_prob.items()):
            out.append({"user": name, "problem": list(key),
                        "first_attempt": min(
                            s["submitted_at"] for s in ss).isoformat(),
                        "solved": any(s["verdict"] == "OK" for s in ss)})
    return out


def main():
    db = SessionLocal()
    try:
        results = {
            "generated_at": datetime.now(timezone.utc).isoformat().replace(
                "+00:00", "Z"),
            "random_seeds": [random_seed_run(db, s) for s in RANDOM_SEEDS],
            "by_time_cutoffs_demo_only": [],
            "combined_by_time_primary_cutoff": None,
            "combined_by_time_relative_cutoff": None,
            "real_rows_first_attempts": real_rows_first_attempts(db),
        }
        for c in CUTOFFS:
            out, _, _, _, _, _, _ = bt.protocol_b(datetime.fromisoformat(c))
            results["by_time_cutoffs_demo_only"].append(out)
        results["combined_by_time_primary_cutoff"] = combined_by_time(
            db, datetime.fromisoformat(PRIMARY_CUTOFF))
        rel = relative_cutoff(db)
        rel_out = combined_by_time(db, rel)
        rel_out["cutoff_rule"] = "80th percentile of first-attempt times"
        results["combined_by_time_relative_cutoff"] = rel_out
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        print(json.dumps(results, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()
