"""Recommender + solvability backtest (Batch 3).

Protocols (see specs/batch3/spec.md):
  A. Random stratified 80/20 split (the shipped training protocol) --
     adds log-loss, an Elo baseline and a calibration table.
  B. By-time split at CUTOFF -- leakage-free forward evaluation.
  C. Recommender precision@k at the cutoff -- rule score vs ML prob vs
     Elo vs random, on problems attempted after the cutoff.

Run from the backend dir with the venv:
    python scripts/backtest.py [--cutoff 2026-10-01] [--retrain]
Prints a human-readable report and writes scripts/backtest-results.json.
The CF problemset is fetched live once and cached at
scripts/problemset-cache.json (gitignored); if Codeforces is unreachable
and no cache exists, protocol C reports "not run".
"""

import argparse
import asyncio
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import ml, seed  # noqa: E402
from app.cf import cf  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services import MIN_SCORE_THRESHOLD  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(_HERE, "backtest-results.json")
CACHE_PATH = os.path.join(_HERE, "problemset-cache.json")
DEFAULT_CUTOFF = "2026-10-01"


def elo_prob(user_rating, problem_rating):
    """Rating-gap-only expected solve probability (standard Elo curve)."""
    return 1.0 / (1.0 + 10.0 ** ((problem_rating - user_rating) / 400.0))


def calibration_table(p, y, bins=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)):
    """Predicted-probability bins vs actual solve rate. Empty bins report
    n=0 with null rates -- never hidden, never smoothed."""
    out = []
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=int)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (p >= lo) & (p <= hi) if hi >= 1.0 else (p >= lo) & (p < hi)
        n = int(mask.sum())
        out.append({
            "bin": "%.1f-%.1f" % (lo, hi),
            "n": n,
            "mean_predicted": round(float(p[mask].mean()), 3) if n else None,
            "actual_solve_rate": round(float(y[mask].mean()), 3) if n else None,
        })
    return out


def _top_tags_for(subs, min_count=5, limit=12):
    counts = Counter()
    for s in subs:
        for t in s["tags"]:
            counts[t] += 1
    return sorted(
        (t for t, c in counts.items() if c >= min_count),
        key=lambda t: -counts[t])[:limit]


# Batch 8: the leakage-free row builder lives in app.ml now (single
# implementation — the training path reuses it for the artifact's
# by_time block). Kept as an alias so protocol B and the Batch 3
# tests are untouched.
time_aware_rows = ml.time_aware_rows


def rule_score(tags, problem_rating, user_rating, weak, attempted):
    """The shipped recommendation score (services.recommend), reimplemented
    for the demo persona (no DB user). `attempted` = already tried before
    the cutoff (P=100) else 60. Returns (score, factors)."""
    weak_hits = [weak[t] for t in tags if t in weak]
    w = max((h["weak_score"] for h in weak_hits), default=0.0) * 100
    target = user_rating + 100
    d = max(0.0, 100 - abs(problem_rating - target) * 0.5)
    if weak_hits:
        top = max(weak_hits, key=lambda h: h["weak_score"])
        r = (1 - top["recent_acceptance"]) * 100
    else:
        r = 50.0
    prio = 100.0 if attempted else 60.0
    score = round(0.35 * w + 0.30 * d + 0.20 * r + 0.15 * prio)
    return score, {"w": round(w, 1), "d": round(d, 1),
                   "r": round(r, 1), "p": round(prio, 1)}


def features_for_problem(problem_rating, tags, key, user_rating, stats_pre,
                         top_tags, prev_attempts=0):
    """Model features for one candidate problem, same construction as
    ml._build_rows (tag acceptance excludes the problem itself)."""
    min_acc, mean_acc = ml._tag_acceptance_excl(stats_pre, tags, key)
    feats = {
        "user_rating": user_rating,
        "problem_rating": problem_rating,
        "rating_diff": problem_rating - user_rating,
        "min_tag_acc": min_acc,
        "mean_tag_acc": mean_acc,
        "prev_attempts": prev_attempts,
    }
    for t in top_tags:
        feats["tag_" + t] = 1.0 if t in tags else 0.0
    return feats


def _eval_candidates(X_tr, y_tr, X_te, y_te):
    """CV + held-out metrics for every candidate on one split. Returns
    (results, fitted_models, rf_test_probabilities)."""
    cv = StratifiedKFold(5, shuffle=True, random_state=ml.RANDOM_STATE)
    results, fitted, rf_test_p = {}, {}, None
    for name, model in ml._candidates().items():
        cv_p = cross_val_predict(model, X_tr, y_tr, cv=cv,
                                 method="predict_proba")[:, 1]
        cv_m = ml._metrics(cv_p, y_tr)
        model.fit(X_tr, y_tr)
        fitted[name] = model
        test_p = model.predict_proba(X_te)[:, 1]
        test_m = ml._metrics(test_p, y_te)
        extreme = float(((test_p < 0.05) | (test_p > 0.95)).mean())
        results[name] = {"cv_auc": cv_m["auc"], "cv_brier": cv_m["brier"],
                         "cv_logloss": cv_m["logloss"],
                         "test_extreme_share": round(extreme, 3),
                         **{"test_" + k: v for k, v in test_m.items()}}
        if name == "random_forest":
            rf_test_p = test_p
    return results, fitted, rf_test_p


def protocol_a(db):
    """Random stratified 80/20 -- the shipped training protocol -- plus
    log-loss (now in ml._metrics), the Elo baseline and a calibration
    table for the shipped RF."""
    rows, top_tags, sources = ml.collect_rows(db)
    feature_names = ml._feature_names(top_tags)
    X, y, base = ml._rows_to_xy(rows, feature_names)
    try:
        X_tr, X_te, y_tr, y_te, b_tr, b_te = train_test_split(
            X, y, base, test_size=0.2, random_state=ml.RANDOM_STATE,
            stratify=y)
    except ValueError:
        X_tr, X_te, y_tr, y_te, b_tr, b_te = train_test_split(
            X, y, base, test_size=0.2, random_state=ml.RANDOM_STATE)
    elo_te = np.array([elo_prob(int(r), int(p))
                       for r, p in zip(X_te[:, 0], X_te[:, 1])])
    out = {
        "n_rows": len(rows),
        "sources": sources,
        "split": {"train": int(len(y_tr)), "test": int(len(y_te)),
                  "solved_total": int(y.sum()),
                  "unsolved_total": int(len(y) - y.sum()),
                  "test_solved": int(y_te.sum()),
                  "test_unsolved": int(len(y_te) - y_te.sum())},
        "baseline_rule": ml._metrics(b_te, y_te),
        "baseline_elo": ml._metrics(elo_te, y_te),
    }
    results, _, rf_test_p = _eval_candidates(X_tr, y_tr, X_te, y_te)
    out.update(results)
    out["calibration_random_forest_test"] = calibration_table(rf_test_p, y_te)
    return out


def protocol_b(cutoff):
    """By-time split on the demo persona only (real rows are too few to
    split). Features and labels as documented in time_aware_rows."""
    demo_subs, demo_hist, demo_rating = ml._demo_set()
    pre = [s for s in demo_subs if s["submitted_at"] < cutoff]
    top_tags = _top_tags_for(pre)
    train_rows, test_rows, stats_pre, weak_pre = time_aware_rows(
        demo_subs, demo_hist, demo_rating, top_tags, cutoff)
    feature_names = ml._feature_names(top_tags)
    X_tr, y_tr, b_tr = ml._rows_to_xy(train_rows, feature_names)
    X_te, y_te, b_te = ml._rows_to_xy(test_rows, feature_names)
    elo_te = np.array([elo_prob(int(r), int(p))
                       for r, p in zip(X_te[:, 0], X_te[:, 1])])
    out = {
        "cutoff": cutoff.isoformat(),
        "n_train": len(train_rows), "n_test": len(test_rows),
        "train_solved": int(y_tr.sum()), "test_solved": int(y_te.sum()),
        "top_tags": top_tags,
        "baseline_rule": ml._metrics(b_te, y_te),
        "baseline_elo": ml._metrics(elo_te, y_te),
    }
    results, fitted, rf_test_p = _eval_candidates(X_tr, y_tr, X_te, y_te)
    out.update(results)
    out["calibration_random_forest_test"] = calibration_table(rf_test_p, y_te)
    return (out, fitted["random_forest"], feature_names, stats_pre,
            weak_pre, top_tags, test_rows)


def load_problemset():
    """Live CF problemset, cached locally. Returns None when unreachable
    and no cache exists (the caller reports "not run")."""
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                cached = json.load(f)
            return cached["problems"]
        except (OSError, ValueError, KeyError):
            pass
    try:
        problems = asyncio.run(cf.problemset())
    except Exception:
        return None
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                       "problems": problems}, f)
    except OSError:
        pass
    return problems


def protocol_c(cutoff, rf_model, feature_names, stats_pre, weak_pre,
               top_tags, test_rows):
    """Recommender precision@k, forward in time.

    At the cutoff the demo persona ranks the live CF problemset (rating
    band [rating, rating+200], problems never attempted before the cutoff).
    Top-3/5/10 of each ranking are checked against what the user actually
    attempted after the cutoff and solved. The rule ranking applies the
    shipped MIN_SCORE_THRESHOLD (it is the shipped behaviour); ML, Elo
    and random rank the full pool. A second view (C2) scores each method
    as a solve predictor on the 36 post-cutoff problems directly.
    """
    demo_subs, demo_hist, demo_rating = ml._demo_set()
    rating_at_cutoff = ml._rating_at(demo_hist, cutoff, demo_rating)
    by_prob = defaultdict(list)
    for s in demo_subs:
        by_prob[s["problem_key"]].append(s)
    attempted_pre = {k for k, ss in by_prob.items()
                     if min(s["submitted_at"] for s in ss) < cutoff}
    post = {r["key"]: r["label"] for r in test_rows}
    problems = load_problemset()
    if problems is None:
        return {"ran": False,
                "reason": "Codeforces problemset unreachable and no cache exists"}
    lo, hi = rating_at_cutoff, rating_at_cutoff + 200
    pool = []
    for p in problems:
        pr = p.get("rating")
        if pr is None or pr < lo or pr > hi:
            continue
        key = (p["contestId"], p["index"])
        if key in attempted_pre:
            continue
        pool.append(p)
    rule_ranked, ml_feats, elo_ranked = [], [], []
    for p in pool:
        key = (p["contestId"], p["index"])
        tags = p.get("tags", [])
        s, _ = rule_score(tags, p["rating"], rating_at_cutoff, weak_pre, False)
        if s >= MIN_SCORE_THRESHOLD:
            rule_ranked.append((s, key))
        ml_feats.append(features_for_problem(
            p["rating"], tags, key, rating_at_cutoff, stats_pre, top_tags, 0))
        elo_ranked.append((elo_prob(rating_at_cutoff, p["rating"]), key))
    rule_ranked.sort(key=lambda t: -t[0])
    X_pool = np.array([[f[k] for k in feature_names] for f in ml_feats],
                      dtype=float)
    ml_probs = rf_model.predict_proba(X_pool)[:, 1]
    ml_ranked = sorted(zip(ml_probs.tolist(),
                           [(p["contestId"], p["index"]) for p in pool]),
                       key=lambda t: -t[0])
    elo_ranked.sort(key=lambda t: -t[0])
    rng = random.Random(42)
    rand_keys = [(p["contestId"], p["index"]) for p in pool]
    rng.shuffle(rand_keys)
    rankings = {
        "rule_score": [k for _, k in rule_ranked],
        "ml_probability": [k for _, k in ml_ranked],
        "elo": [k for _, k in elo_ranked],
        "random": rand_keys,
    }
    pool_keys = {(p["contestId"], p["index"]) for p in pool}
    in_pool = [k for k in post if k in pool_keys]
    by_key = {(p["contestId"], p["index"]): p for p in problems}
    in_band = [k for k in post
               if k in by_key and by_key[k].get("rating") is not None
               and lo <= by_key[k]["rating"] <= hi]
    out = {"ran": True, "rating_at_cutoff": rating_at_cutoff,
           "pool_size": len(pool), "rule_pool_size": len(rule_ranked),
           "post_cutoff_attempted": len(post),
           "post_cutoff_solved": int(sum(post.values())),
           "post_cutoff_in_pool": len(in_pool),
           "post_cutoff_in_band": len(in_band),
           "base_solve_rate_post_cutoff":
               round(sum(post.values()) / len(post), 3) if post else None,
           "topk": {}}
    for name, keys in rankings.items():
        per_k = {}
        for k in (3, 5, 10, 50, 100):
            topk = keys[:k]
            attempted = [key for key in topk if key in post]
            solved = [key for key in attempted if post[key] == 1]
            per_k["k%d" % k] = {
                "attempted": len(attempted),
                "solved": len(solved),
                "precision": (round(len(solved) / len(attempted), 3)
                              if attempted else None),
            }
        out["topk"][name] = per_k
    X_te, y_te, b_te = ml._rows_to_xy(test_rows, feature_names)
    elo_te = np.array([elo_prob(int(r), int(p))
                       for r, p in zip(X_te[:, 0], X_te[:, 1])])
    ml_te = rf_model.predict_proba(X_te)[:, 1]
    out["predictor_on_post_cutoff"] = {
        "rule_score": ml._metrics(b_te, y_te),
        "ml_probability": ml._metrics(ml_te, y_te),
        "elo": ml._metrics(elo_te, y_te),
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", default=DEFAULT_CUTOFF)
    ap.add_argument("--retrain", action="store_true",
                    help="also retrain the shipped model (demo + dev DB) "
                         "with the new log-loss metric")
    args = ap.parse_args()
    cutoff = datetime.fromisoformat(args.cutoff)
    db = SessionLocal()
    try:
        results = {
            "cutoff": args.cutoff,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "protocol_a_random_split": protocol_a(db),
        }
        (b_out, rf, feature_names, stats_pre, weak_pre, top_tags,
         test_rows) = protocol_b(cutoff)
        results["protocol_b_by_time"] = b_out
        results["protocol_c_precision_at_k"] = protocol_c(
            cutoff, rf, feature_names, stats_pre, weak_pre, top_tags,
            test_rows)
        if args.retrain:
            results["retrain"] = ml.train_model(db)
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        print(json.dumps(results, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()
