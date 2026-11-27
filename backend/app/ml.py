"""ML solvability prediction (Phase 3).

Predicts P(user eventually solves this problem) from submission history.

DESIGN (validated on the demo data before shipping — the evaluation
numbers are stored in the model artifact):
- One training row per (user, problem): label = 1 if the user eventually
  solved it, 0 otherwise. Features are all computable at recommendation
  time: user rating at first attempt (interpolated rating history),
  problem rating, rating difference, per-tag acceptance (min/mean across
  the problem's tags, target problem EXCLUDED), previous attempts on the
  problem, and one-hot tags.
- Baseline FIRST: the rule-based recommendation score (0.35W+0.30D+0.20R
  +0.15P, blueprint SS6) as a probability (score/100). It is a
  practice-priority score, not a solvability score — on the demo data it
  scores BELOW chance (test AUC 0.467), because it deliberately rewards
  weak tags and harder problems. The ML model has to beat it to ship.
- Candidates, in order: Logistic Regression, Random Forest, Gradient
  Boosting (HistGradientBoosting). Selection by 5-fold CV AUC on the
  train split, confirmed on a stratified held-out test set.
- The deep Random Forest (CV AUC 0.960) and HistGB (CV AUC 0.977) were
  REJECTED: they overfit the 197 demo rows and predict degenerate
  values (1300-rated graphs 0.08 when the true rate is ~0.49; HistGB
  predicts 0.00/0.99). The shipped model is a CONSTRAINED Random
  Forest (max_depth=4, min_samples_leaf=10): test AUC 0.821, Brier
  0.148 vs baseline 0.467 / 0.358, and sane predictions (weak tags
  ~0.35-0.55, strong tags ~0.8).
- Sigmoid calibration was tried and REJECTED (CV Brier 0.157 vs 0.143
  uncalibrated), so the shipped model is uncalibrated.
- SELECTION BIAS, stated plainly: the training rows are problems the
  user already attempted — never-attempted problems (most of the
  problemset) are not in the data. The model estimates "will you solve
  a problem like the ones you tried", not "will you solve any problem".
  Demo rows are SYNTHETIC (seed.py, rng-generated with known per-tag
  solve rates), so the model mostly reflects the demo persona until
  real submissions accumulate. The artifact records its data sources
  and the UI labels them honestly.

The model artifact is a joblib file (backend/ml_model.joblib, gitignored)
holding the estimator + feature list + full evaluation metadata. If the
file is missing (fresh deploy, ephemeral disk), the first status /
prediction call trains it lazily; a background thread also trains at
startup. Training on ~200 rows takes a few seconds.
Retraining is MANUAL (Settings -> Retrain model, or POST /ml/retrain):
a sync does not auto-retrain, so the artifact keeps serving the previous
model until someone retrains -- the UI labels the training data honestly
("Trained on demo data" until real rows are folded in by a retrain).
"""
import os
import threading
from collections import defaultdict
from datetime import datetime, timedelta

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import seed
from .models import CfAccount, Problem, RatingHistory, Submission, User

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(_BACKEND_DIR, "ml_model.joblib")

MIN_ROWS_TO_TRAIN = 40
TOP_TAG_LIMIT = 12
MIN_TAG_COUNT = 5
RANDOM_STATE = 42

# Weak-topic weights (blueprint SS5) — mirrors services.tag_stats exactly,
# so the baseline mirror below agrees with services.recommend().
W_ACCEPTANCE = 0.40
W_WRONG = 0.25
W_RECENT = 0.20
W_DIFFICULTY = 0.15
MIN_ATTEMPTS_FOR_WEAK = 10
WEAK_SCORE_THRESHOLD = 0.50
RECENT_DAYS = 30

_train_lock = threading.Lock()
_training = {"running": False}
_model_cache: dict = {"mtime": None, "artifact": None}


def artifact_exists() -> bool:
    return os.path.exists(MODEL_PATH)


def training_running() -> bool:
    return _training["running"]


# ---------------------------------------------------------------------------
# Plain-data layer: everything below works on dicts, so the DB path and the
# demo-seed path share one dataset builder.
# Submission dict: {problem_key, tags, verdict, submitted_at (datetime),
#                   problem_rating}
# ---------------------------------------------------------------------------

def _tag_stats(rows: list[dict]) -> dict[str, dict]:
    """Per-tag stats with the blueprint SS5 formula. att_set / sol_set are
    the unique attempted / solved problem keys — used to exclude a target
    problem from its own tag acceptance (no leakage)."""
    recent_cutoff = datetime.utcnow() - timedelta(days=RECENT_DAYS)
    per: dict[str, dict] = defaultdict(
        lambda: {"att": set(), "sol": set(), "wrong": 0, "tot": 0,
                 "recent_sol": 0, "recent_tot": 0,
                 "rating_sum": 0, "rated": 0})
    for r in rows:
        for tag in r["tags"]:
            st = per[tag]
            st["tot"] += 1
            st["att"].add(r["problem_key"])
            if r.get("problem_rating") is not None:
                st["rating_sum"] += r["problem_rating"]
                st["rated"] += 1
            if r["submitted_at"] >= recent_cutoff:
                st["recent_tot"] += 1
                if r["verdict"] == "OK":
                    st["recent_sol"] += 1
            if r["verdict"] == "OK":
                st["sol"].add(r["problem_key"])
            else:
                st["wrong"] += 1
    out = {}
    for tag, st in per.items():
        att, sol = len(st["att"]), len(st["sol"])
        acc = sol / att if att else 0.0
        wrong_ratio = st["wrong"] / st["tot"] if st["tot"] else 0.0
        recent_acc = (st["recent_sol"] / st["recent_tot"]
                      if st["recent_tot"] else acc)
        avg_rating = st["rating_sum"] / st["rated"] if st["rated"] else None
        diff_norm = (max(0.0, min(1.0, (avg_rating - 800) / 1600))
                     if avg_rating is not None else 0.0)
        weak_score = round(
            W_ACCEPTANCE * (1 - acc) + W_WRONG * wrong_ratio
            + W_RECENT * (1 - recent_acc) + W_DIFFICULTY * diff_norm, 3)
        out[tag] = {
            "acceptance": acc, "weak_score": weak_score,
            "weak": att >= MIN_ATTEMPTS_FOR_WEAK and weak_score >= WEAK_SCORE_THRESHOLD,
            "attempted": att, "solved": sol,
            "recent_acceptance": round(recent_acc, 2),
            "att_set": st["att"], "sol_set": st["sol"],
        }
    return out


def _rating_at(history: list[tuple[datetime, int]], ts: datetime,
               fallback: int) -> int:
    """User rating at a moment: latest contest rating at or before it,
    else the earliest known, else the fallback (current rating / 1200)."""
    if not history:
        return fallback
    cur = history[0][1]
    for d, r in history:
        if d <= ts:
            cur = r
        else:
            break
    return cur


def _baseline_score(stats: dict, weak: dict, user_rating: int,
                    problem_rating: int, tags: list[str]) -> int:
    """The rule-based recommendation score (services.recommend formula) for
    one problem, as a 0-100 score. Training rows are all attempted
    problems, so the P factor is always 100 here."""
    weak_hits = [weak[t] for t in tags if t in weak]
    w = max((h["weak_score"] for h in weak_hits), default=0.0) * 100
    target = user_rating + 100
    d = max(0.0, 100 - abs(problem_rating - target) * 0.5)
    if weak_hits:
        top = max(weak_hits, key=lambda h: h["weak_score"])
        r = (1 - top["recent_acceptance"]) * 100
    else:
        r = 50.0
    return round(0.35 * w + 0.30 * d + 0.20 * r + 0.15 * 100.0)


def _tag_acceptance_excl(stats: dict, tags: list[str],
                         key: tuple) -> tuple[float, float]:
    """Min/mean tag acceptance EXCLUDING the target problem (no leakage).
    Falls back to 0.5 when a tag has no other problems behind it."""
    accs = []
    for tag in tags:
        st = stats.get(tag)
        if st is None:
            continue
        att = len(st["att_set"] - {key})
        sol = len(st["sol_set"] - {key})
        accs.append(sol / att if att > 0 else 0.5)
    if not accs:
        return 0.5, 0.5
    return min(accs), sum(accs) / len(accs)


def _build_rows(submissions: list[dict],
                rating_history: list[tuple[datetime, int]],
                current_rating: int | None,
                top_tags: list[str]) -> list[dict]:
    """One row per (user, problem). Label = 1 if eventually solved."""
    by_prob: dict[tuple, list[dict]] = defaultdict(list)
    for s in submissions:
        by_prob[s["problem_key"]].append(s)
    stats = _tag_stats(submissions)
    weak = {t: v for t, v in stats.items() if v["weak"]}
    fallback_rating = current_rating or 1200
    rows = []
    for key, subs in by_prob.items():
        prob = subs[0]
        if prob["problem_rating"] is None:
            continue  # unrated problems cannot train the rating features
        first = min(s["submitted_at"] for s in subs)
        user_rating = _rating_at(rating_history, first, fallback_rating)
        min_acc, mean_acc = _tag_acceptance_excl(stats, prob["tags"], key)
        label = 1 if any(s["verdict"] == "OK" for s in subs) else 0
        score = _baseline_score(stats, weak, user_rating,
                                prob["problem_rating"], prob["tags"])
        feats = {
            "user_rating": user_rating,
            "problem_rating": prob["problem_rating"],
            "rating_diff": prob["problem_rating"] - user_rating,
            "min_tag_acc": min_acc,
            "mean_tag_acc": mean_acc,
            "prev_attempts": len(subs),
        }
        for t in top_tags:
            feats[f"tag_{t}"] = 1.0 if t in prob["tags"] else 0.0
        rows.append({"features": feats, "label": label,
                     "baseline_score": score, "key": key})
    return rows


def _feature_names(top_tags: list[str]) -> list[str]:
    return ["user_rating", "problem_rating", "rating_diff",
            "min_tag_acc", "mean_tag_acc", "prev_attempts"] + [
            f"tag_{t}" for t in top_tags]


def _rows_to_xy(rows: list[dict], feature_names: list[str]):
    X = np.array([[r["features"][k] for k in feature_names] for r in rows],
                 dtype=float)
    y = np.array([r["label"] for r in rows], dtype=int)
    base = np.array([r["baseline_score"] for r in rows], dtype=float) / 100.0
    return X, y, base


def _metrics(p: np.ndarray, y: np.ndarray) -> dict:
    pred = (p >= 0.5).astype(int)
    out = {"accuracy": round(float(accuracy_score(y, pred)), 3),
           "brier": round(float(brier_score_loss(y, p)), 3)}
    try:
        out["auc"] = round(float(roc_auc_score(y, p)), 3)
    except ValueError:
        out["auc"] = None  # single-class split
    return out


def _candidates():
    """Model candidates in blueprint order. The Random Forest is
    deliberately CONSTRAINED (depth 4, leaf 10): the deep forest and
    HistGB overfit ~200 rows and predict degenerate 0.00/0.99 values."""
    return {
        "logreg": make_pipeline(
            StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=4, min_samples_leaf=10,
            random_state=RANDOM_STATE, n_jobs=-1),
        "hist_gb": HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.08, max_depth=3,
            min_samples_leaf=10, random_state=RANDOM_STATE),
    }


# ---------------------------------------------------------------------------
# Data collection: demo seed + every DB user with submissions.
# ---------------------------------------------------------------------------

def _demo_set() -> tuple[list[dict], list[tuple[datetime, int]], int]:
    subs = [{
        "problem_key": (s["contest_id"], s["index"]),
        "tags": s["tags"], "verdict": s["verdict"],
        "submitted_at": datetime.fromisoformat(s["submitted_at"]),
        "problem_rating": s["rating"],
    } for s in seed.SUBMISSIONS]
    hist = sorted(
        (datetime.fromisoformat(p["date"]), p["rating"])
        for p in seed.RATING_HISTORY)
    return subs, hist, seed.RATING


def _db_sets(db) -> list[tuple[list[dict], list[tuple[datetime, int]], int, str]]:
    """One (submissions, rating history, current rating, handle) tuple per
    DB user with submissions."""
    sets = []
    for user in db.query(User).all():
        subs_q = (
            db.query(Submission, Problem)
            .join(Problem, Submission.problem_id == Problem.id)
            .filter(Submission.user_id == user.id)
            .all()
        )
        if not subs_q:
            continue
        subs = [{
            "problem_key": (p.contest_id, p.index),
            "tags": p.tags or [], "verdict": s.verdict,
            "submitted_at": s.submitted_at, "problem_rating": p.rating,
        } for s, p in subs_q]
        hist = sorted(
            (r.rated_at, r.rating)
            for r in db.query(RatingHistory).filter_by(user_id=user.id).all())
        account = db.query(CfAccount).filter_by(user_id=user.id).first()
        handle = account.handle if account else f"user-{user.id}"
        sets.append((subs, hist, user.current_rating, handle))
    return sets


def collect_rows(db=None) -> tuple[list[dict], list[str], dict]:
    """All training rows: demo seed + DB users. Top tags are global
    (count >= 5 across ALL data, capped at 12). Returns
    (rows, top_tags, sources)."""
    demo_subs, demo_hist, demo_rating = _demo_set()
    sets = [(demo_subs, demo_hist, demo_rating, "demo_coder (seed)")]
    if db is not None:
        sets.extend(_db_sets(db))
    tag_counts: dict[str, int] = defaultdict(int)
    for subs, _, _, _ in sets:
        for s in subs:
            for t in s["tags"]:
                tag_counts[t] += 1
    top_tags = sorted(
        (t for t, c in tag_counts.items() if c >= MIN_TAG_COUNT),
        key=lambda t: -tag_counts[t])[:TOP_TAG_LIMIT]
    rows: list[dict] = []
    sources: dict[str, int] = {}
    for subs, hist, rating, name in sets:
        rs = _build_rows(subs, hist, rating, top_tags)
        if rs:
            rows.extend(rs)
            sources[name] = len(rs)
    return rows, top_tags, sources


# ---------------------------------------------------------------------------
# Training / persistence / prediction
# ---------------------------------------------------------------------------

def train_model(db=None) -> dict:
    """Trains, evaluates and (if it beats the baseline) ships the model.
    Returns the evaluation report — also stored in the artifact. A second
    concurrent call returns a 'training already running' report instead of
    training twice."""
    with _train_lock:
        if _training["running"]:
            return {"trained": False, "reason": "training already running"}
        _training["running"] = True
        try:
            return _train_model_locked(db)
        finally:
            _training["running"] = False


def _train_model_locked(db=None) -> dict:
    rows, top_tags, sources = collect_rows(db)
    n = len(rows)
    demo_rows = sources.get("demo_coder (seed)", 0)
    real_rows = n - demo_rows
    if n < MIN_ROWS_TO_TRAIN:
        return {"trained": False, "reason": "not enough data",
                "n_rows": n, "min_rows": MIN_ROWS_TO_TRAIN,
                "sources": sources}
    feature_names = _feature_names(top_tags)
    X, y, base = _rows_to_xy(rows, feature_names)
    n_solved = int(y.sum())
    # Stratified hold-out; fall back to a plain split if a class is tiny.
    try:
        X_tr, X_te, y_tr, y_te, b_tr, b_te = train_test_split(
            X, y, base, test_size=0.2, random_state=RANDOM_STATE, stratify=y)
    except ValueError:
        X_tr, X_te, y_tr, y_te, b_tr, b_te = train_test_split(
            X, y, base, test_size=0.2, random_state=RANDOM_STATE)
    cv = StratifiedKFold(5, shuffle=True, random_state=RANDOM_STATE)
    evaluation: dict = {
        "split": {"train": int(len(y_tr)), "test": int(len(y_te)),
                  "solved_total": n_solved,
                  "unsolved_total": int(n - n_solved)},
        "baseline": _metrics(b_te, y_te),
        "baseline_note": ("The rule-based score is a practice-priority "
                          "score, not a solvability score — it rewards weak "
                          "tags and harder problems, so it scores below "
                          "chance as a probability."),
    }
    results: dict[str, dict] = {}
    for name, model in _candidates().items():
        cv_p = cross_val_predict(model, X_tr, y_tr, cv=cv,
                                 method="predict_proba")[:, 1]
        cv_m = _metrics(cv_p, y_tr)
        model.fit(X_tr, y_tr)
        test_m = _metrics(model.predict_proba(X_te)[:, 1], y_te)
        results[name] = {
            "cv_auc": cv_m["auc"], "cv_brier": cv_m["brier"],
            **{f"test_{k}": v for k, v in test_m.items()},
        }
    # Calibration check on the shipped candidate: keep it only if the CV
    # Brier improves (on the demo data it does not: 0.157 vs 0.143).
    rf = _candidates()["random_forest"]
    cal = CalibratedClassifierCV(rf, method="sigmoid", cv=3)
    cal_p = cross_val_predict(cal, X_tr, y_tr, cv=cv, method="predict_proba")[:, 1]
    cal_brier = _metrics(cal_p, y_tr)["brier"]
    raw_brier = results["random_forest"]["cv_brier"]
    use_calibrated = cal_brier < raw_brier
    evaluation.update(results)
    evaluation["calibration"] = {
        "tried": "sigmoid (CalibratedClassifierCV, cv=3)",
        "cv_brier_uncalibrated": raw_brier,
        "cv_brier_calibrated": cal_brier,
        "shipped_calibrated": bool(use_calibrated),
    }
    # Ship rule: the constrained forest must beat the baseline on BOTH
    # held-out AUC and Brier. (On the demo data it does, by a wide margin.)
    rf_test = results["random_forest"]
    base_test = evaluation["baseline"]
    shipped = (
        rf_test["test_auc"] is not None and base_test["auc"] is not None
        and rf_test["test_auc"] > base_test["auc"]
        and rf_test["test_brier"] < base_test["brier"])
    ship_reason = (
        "Random Forest beats the baseline on held-out AUC and Brier."
        if shipped else
        "No model beat the baseline on the held-out set — rule-based "
        "scores stay, no ML model shipped.")
    final_model = rf
    if shipped and use_calibrated:
        final_model = CalibratedClassifierCV(rf, method="sigmoid", cv=3)
    final_model.fit(X, y)  # refit on ALL rows for the shipped artifact
    artifact = {
        "model": final_model,
        "feature_names": feature_names,
        "top_tags": top_tags,
        "metadata": {
            "model_type": ("RandomForest (n=300, max_depth=4, "
                           "min_samples_leaf=10)" + (" + sigmoid calibration"
                                                      if shipped and use_calibrated else "")),
            "trained_at": datetime.utcnow().isoformat() + "Z",  # UTC; the UI parses it as UTC
            "n_rows": n,
            "n_solved": n_solved,
            "sources": sources,
            "demo_rows": demo_rows,
            "real_rows": real_rows,
            "features": feature_names,
            "evaluation": evaluation,
            "shipped": bool(shipped),
            "ship_reason": ship_reason,
            "bias_note": ("Rows are problems the user already attempted; "
                          "never-attempted problems are not in the data. "
                          "Demo rows are synthetic (seed.py). Treat the "
                          "probability as a hint, not a guarantee."),
        },
    }
    joblib.dump(artifact, MODEL_PATH)
    _model_cache["mtime"] = os.path.getmtime(MODEL_PATH)
    _model_cache["artifact"] = artifact
    return {"trained": True, **artifact["metadata"]}


def _load_artifact():
    if not os.path.exists(MODEL_PATH):
        return None
    mtime = os.path.getmtime(MODEL_PATH)
    if _model_cache["artifact"] is not None and _model_cache["mtime"] == mtime:
        return _model_cache["artifact"]
    try:
        artifact = joblib.load(MODEL_PATH)
    except Exception:
        return None
    _model_cache["mtime"] = mtime
    _model_cache["artifact"] = artifact
    return artifact


def model_status(db=None, own_handle=None) -> dict:
    """Public status payload for the UI.

    Batch 1 (audit F5): NEVER trains here — training happens only at
    startup (background) or via /ml/retrain (cooldown-gated). If no
    artifact exists yet, the honest answer is "not trained yet".
    Batch 1 (audit F9): per-user sources are scoped to the requesting
    user's own handle; the demo gets aggregates only. The `db` argument
    is kept for signature compatibility and is unused."""
    artifact = _load_artifact()
    if artifact is None:
        return {"trained": False,
                "reason": "Model not trained yet."}
    md = artifact["metadata"]
    ev = md["evaluation"]
    sources = md["sources"]
    scoped_sources = ({own_handle: sources[own_handle]}
                      if own_handle and own_handle in sources else {})
    return {
        "trained": True,
        "model_type": md["model_type"],
        "trained_at": md["trained_at"],
        "n_rows": md["n_rows"],
        "n_solved": md["n_solved"],
        "demo_rows": md["demo_rows"],
        "real_rows": md["real_rows"],
        "sources": scoped_sources,
        "features": md["features"],
        "shipped": md["shipped"],
        "ship_reason": md["ship_reason"],
        "bias_note": md["bias_note"],
        "evaluation": {
            "baseline": ev["baseline"],
            "random_forest": ev["random_forest"],
            "logreg": ev["logreg"],
            "hist_gb": ev["hist_gb"],
            "calibration": ev["calibration"],
        },
    }


def _predict_rows(artifact, user_rating: int, stats: dict,
                  prev_attempts: dict, problems: list[dict]) -> list[dict]:
    """problems: [{contest_id, index, name, rating, tags}]. Returns
    [{contest_id, index, probability}] — probability None when the
    problem is unrated or no model is shipped."""
    if artifact is None or not artifact["metadata"]["shipped"]:
        return [{"contest_id": p["contest_id"], "index": p["index"],
                 "probability": None} for p in problems]
    model = artifact["model"]
    feature_names = artifact["feature_names"]
    top_tags = artifact["top_tags"]
    out = []
    for p in problems:
        if p.get("rating") is None:
            out.append({"contest_id": p["contest_id"], "index": p["index"],
                        "probability": None})
            continue
        tags = p.get("tags", [])
        key = (p["contest_id"], p["index"])
        min_acc, mean_acc = _tag_acceptance_excl(stats, tags, key)
        feats = {
            "user_rating": user_rating,
            "problem_rating": p["rating"],
            "rating_diff": p["rating"] - user_rating,
            "min_tag_acc": min_acc,
            "mean_tag_acc": mean_acc,
            "prev_attempts": prev_attempts.get(key, 0),
        }
        for t in top_tags:
            feats[f"tag_{t}"] = 1.0 if t in tags else 0.0
        x = np.array([[feats.get(k, 0.0) for k in feature_names]], dtype=float)
        prob = float(model.predict_proba(x)[0, 1])
        out.append({"contest_id": p["contest_id"], "index": p["index"],
                    "probability": round(prob, 3)})
    return out


def _user_submission_dicts(db, user_id: int) -> list[dict]:
    rows = (
        db.query(Submission, Problem)
        .join(Problem, Submission.problem_id == Problem.id)
        .filter(Submission.user_id == user_id)
        .all()
    )
    return [{
        "problem_key": (p.contest_id, p.index), "tags": p.tags or [],
        "verdict": s.verdict, "submitted_at": s.submitted_at,
        "problem_rating": p.rating,
    } for s, p in rows]


def _prev_attempts_map(submissions: list[dict]) -> dict:
    prev: dict[tuple, int] = defaultdict(int)
    for s in submissions:
        prev[s["problem_key"]] += 1
    return dict(prev)


def predict_for_user(db, user, problems: list[dict], handle=None) -> dict:
    """Predictions for one DB user. `problems` are recommendation-shaped
    dicts ({contest_id, index, name, rating, tags}). No lazy training
    (audit F5) — without an artifact every probability is None."""
    artifact = _load_artifact()
    subs = _user_submission_dicts(db, user.id)
    stats = _tag_stats(subs)
    prev = _prev_attempts_map(subs)
    rating = user.current_rating or 1200
    return {"predictions": _predict_rows(artifact, rating, stats, prev, problems),
            "model": model_status(db, handle) if artifact else {"trained": False}}


def predict_for_demo(problems: list[dict]) -> dict:
    """Predictions for the demo persona (rating 1478, seed history)."""
    artifact = _load_artifact()
    subs, _, _ = _demo_set()
    stats = _tag_stats(subs)
    prev = _prev_attempts_map(subs)
    return {"predictions": _predict_rows(artifact, seed.RATING, stats, prev, problems),
            "model": model_status(None) if artifact else {"trained": False}}


if __name__ == "__main__":
    # python -m app.ml — trains on demo data only (no DB) and prints the
    # evaluation report.
    import json

    report = train_model(None)
    print(json.dumps(report, indent=2, default=str))
