"""Analytics: weak topics, recommendations, streak, heatmap.

Weak-topic model (blueprint §5 — a rule-based HEURISTIC, not a validated
score). A tag counts as weak only with enough data (>= 10 unique problems
attempted) and a high weakness score:

    weak_score = 0.40 * (1 - acceptance)
               + 0.25 * wrong_ratio          (wrong subs / all subs)
               + 0.20 * (1 - recent_acceptance)  (last 30 days)
               + 0.15 * difficulty_norm      (avg attempted rating, 800..2400)

weak = attempted >= 10 AND weak_score >= 0.50.

Recommendation scoring (blueprint §6): Score = 0.35W + 0.30D + 0.20R + 0.15P
(W weak-topic relevance, D difficulty suitability, R recent learning need,
P practice priority), every factor normalised 0–100.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from .models import CfAccount, Problem, ProblemPreference, Revision, Submission, User

INTERVALS = [1, 3, 7, 14, 30]
MIN_ATTEMPTS_FOR_WEAK = 10
WEAK_SCORE_THRESHOLD = 0.50
RECENT_DAYS = 30

# Weak-score weights (blueprint §5).
W_ACCEPTANCE = 0.40
W_WRONG = 0.25
W_RECENT = 0.20
W_DIFFICULTY = 0.15


def get_cf_account(db: Session, user_id: int) -> CfAccount | None:
    return db.query(CfAccount).filter_by(user_id=user_id).first()


def _problem_key(p: Problem) -> str:
    return f"{p.contest_id}{p.index}"


def tag_stats(db: Session, user_id: int) -> list[dict]:
    """Per-tag: attempted, solved, acceptance %, avg wrong attempts, weak
    score + factor breakdown, last solve. Acceptance counts UNIQUE problems,
    never repeat submissions (blueprint §5)."""
    subs = (
        db.query(Submission, Problem)
        .join(Problem, Submission.problem_id == Problem.id)
        .filter(Submission.user_id == user_id)
        .all()
    )
    recent_cutoff = datetime.utcnow() - timedelta(days=RECENT_DAYS)
    per_tag: dict[str, dict] = defaultdict(
        lambda: {"tag": "", "attempted": 0, "solved": 0, "wrong": 0,
                 "total_subs": 0, "recent_solved": 0, "recent_total": 0,
                 "rating_sum": 0, "rated_problems": 0,
                 "solved_problems": set(), "attempted_problems": set(),
                 "last_solve": None}
    )
    for sub, prob in subs:
        for tag in prob.tags or []:
            s = per_tag[tag]
            s["tag"] = tag
            s["total_subs"] += 1
            is_new_problem = prob.id not in s["attempted_problems"]
            s["attempted_problems"].add(prob.id)
            if is_new_problem and prob.rating is not None:
                s["rating_sum"] += prob.rating
                s["rated_problems"] += 1
            if sub.submitted_at >= recent_cutoff:
                s["recent_total"] += 1
                if sub.verdict == "OK":
                    s["recent_solved"] += 1
            if sub.verdict == "OK":
                s["solved_problems"].add(prob.id)
                if s["last_solve"] is None or sub.submitted_at > s["last_solve"]:
                    s["last_solve"] = sub.submitted_at
            else:
                s["wrong"] += 1
    out = []
    for tag, s in per_tag.items():
        attempted = len(s["attempted_problems"])
        solved = len(s["solved_problems"])
        acceptance = solved / attempted if attempted else 0.0
        avg_wrong = s["wrong"] / attempted if attempted else 0.0
        wrong_ratio = s["wrong"] / s["total_subs"] if s["total_subs"] else 0.0
        recent_acc = (s["recent_solved"] / s["recent_total"]
                      if s["recent_total"] else acceptance)
        avg_rating = (s["rating_sum"] / s["rated_problems"]
                      if s["rated_problems"] else None)
        difficulty_norm = 0.0
        if avg_rating is not None:
            difficulty_norm = max(0.0, min(1.0, (avg_rating - 800) / 1600))
        weak_score = round(
            W_ACCEPTANCE * (1 - acceptance)
            + W_WRONG * wrong_ratio
            + W_RECENT * (1 - recent_acc)
            + W_DIFFICULTY * difficulty_norm, 3)
        weak = attempted >= MIN_ATTEMPTS_FOR_WEAK and weak_score >= WEAK_SCORE_THRESHOLD
        out.append({
            "tag": tag,
            "attempted": attempted,
            "solved": solved,
            "acceptance": round(acceptance, 2),
            "avg_wrong_attempts": round(avg_wrong, 1),
            "last_solve": s["last_solve"].isoformat() if s["last_solve"] else None,
            "weak": weak,
            "weak_score": weak_score,
            "factors": {
                "acceptance": round(acceptance, 2),
                "wrong_ratio": round(wrong_ratio, 2),
                "recent_acceptance": round(recent_acc, 2),
                "avg_attempted_rating": round(avg_rating) if avg_rating else None,
            },
        })
    out.sort(key=lambda t: (t["acceptance"], -t["attempted"]))
    return out


def weak_tags(db: Session, user_id: int) -> list[dict]:
    return [t for t in tag_stats(db, user_id) if t["weak"]]


def solved_problem_ids(db: Session, user_id: int) -> set[int]:
    rows = db.query(Submission.problem_id).filter(
        Submission.user_id == user_id, Submission.verdict == "OK"
    ).distinct().all()
    return {r[0] for r in rows}


def attempted_problem_ids(db: Session, user_id: int) -> set[int]:
    rows = db.query(Submission.problem_id).filter(
        Submission.user_id == user_id
    ).distinct().all()
    return {r[0] for r in rows}


def current_streak(db: Session, user_id: int) -> int:
    """Consecutive days (ending today or yesterday) with >= 1 accepted submission."""
    days = {
        r[0].date()
        for r in db.query(Submission.submitted_at)
        .filter(Submission.user_id == user_id, Submission.verdict == "OK")
        .all()
    }
    if not days:
        return 0
    today = date.today()
    cursor = today if today in days else today - timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def heatmap(db: Session, user_id: int, weeks: int = 26) -> list[dict]:
    """Daily accepted-submission counts for the last N weeks (SVG heatmap)."""
    start = date.today() - timedelta(days=weeks * 7 - 1)
    counts: dict[str, int] = defaultdict(int)
    for (ts,) in db.query(Submission.submitted_at).filter(
        Submission.user_id == user_id,
        Submission.verdict == "OK",
        Submission.submitted_at >= datetime.combine(start, datetime.min.time()),
    ).all():
        counts[ts.date().isoformat()] += 1
    days = []
    d = start
    while d <= date.today():
        days.append({"date": d.isoformat(), "count": counts.get(d.isoformat(), 0)})
        d += timedelta(days=1)
    return days


def recent_submissions(db: Session, user_id: int, limit: int = 10) -> list[dict]:
    rows = (
        db.query(Submission, Problem)
        .join(Problem, Submission.problem_id == Problem.id)
        .filter(Submission.user_id == user_id)
        .order_by(Submission.submitted_at.desc())
        .limit(limit)
        .all()
    )
    return [{
        "problem": {"contest_id": p.contest_id, "index": p.index, "name": p.name,
                    "rating": p.rating, "tags": p.tags or []},
        "verdict": s.verdict,
        "language": s.language,
        "submitted_at": s.submitted_at.isoformat(),
    } for s, p in rows]


def recommend(db: Session, user: User, problems: list[dict], limit: int = 12,
              tag: str | None = None, min_rating: int | None = None,
              max_rating: int | None = None, hide_solved: bool = True) -> list[dict]:
    """Rule-based recommendations, scored 0–100 (blueprint §6):
    Score = 0.35W + 0.30D + 0.20R + 0.15P. 'later' and 'dismissed'
    problems are excluded; 'interested' ones stay in the list."""
    solved = solved_problem_ids(db, user.id) if hide_solved else set()
    solved_keys = set()
    if solved:
        for p in db.query(Problem).filter(Problem.id.in_(solved)).all():
            solved_keys.add((p.contest_id, p.index))
    attempted = attempted_problem_ids(db, user.id)
    attempted_keys = set()
    if attempted:
        for p in db.query(Problem).filter(Problem.id.in_(attempted)).all():
            attempted_keys.add((p.contest_id, p.index))
    weak = {t["tag"]: t for t in weak_tags(db, user.id)}
    stats = {t["tag"]: t for t in tag_stats(db, user.id)}
    rating = user.current_rating or 1200
    lo = min_rating if min_rating is not None else rating
    hi = max_rating if max_rating is not None else rating + 200
    excluded = {
        (p.contest_id, p.index)
        for p in db.query(Problem).join(
            ProblemPreference, ProblemPreference.problem_id == Problem.id).filter(
            ProblemPreference.user_id == user.id,
            ProblemPreference.state.in_(("later", "dismissed"))).all()
    }
    target = rating + 100  # difficulty sweet spot: just above current rating
    scored = []
    for p in problems:
        pr = p.get("rating")
        if pr is None or pr < lo or pr > hi:
            continue
        key = (p["contestId"], p["index"])
        if key in solved_keys or key in excluded:
            continue
        tags = p.get("tags", [])
        if tag and tag not in tags:
            continue
        # W — weak-topic relevance: the problem's weakest tag's score.
        weak_hits = [weak[t] for t in tags if t in weak]
        w = max((h["weak_score"] for h in weak_hits), default=0.0) * 100
        # D — difficulty suitability: 100 at target, 0 at ±200 away.
        d = max(0.0, 100 - abs(pr - target) * 0.5)
        # R — recent learning need: how badly the tag went lately.
        if weak_hits:
            weakest = max(weak_hits, key=lambda h: h["weak_score"])
            r = (1 - weakest["factors"]["recent_acceptance"]) * 100
        else:
            r = 50.0
        # P — practice priority: tried-but-unsolved first.
        if key in attempted_keys:
            prio = 100.0
        else:
            prio = 60.0
        score = round(0.35 * w + 0.30 * d + 0.20 * r + 0.15 * prio)
        # Structured "why" — the frontend renders the sentence in the
        # active locale (EN/BN). Never build a sentence here.
        if weak_hits:
            top = max(weak_hits, key=lambda h: h["weak_score"])
            if top["acceptance"] < 0.5:
                why = {"kind": "weak_acceptance", "tag": top["tag"],
                       "acceptance": int(top["acceptance"] * 100),
                       "problem_rating": pr, "user_rating": rating}
            else:
                why = {"kind": "weak_wrong", "tag": top["tag"],
                       "avg_wrong_attempts": top["avg_wrong_attempts"],
                       "problem_rating": pr, "user_rating": rating}
        else:
            why = {"kind": "near_rating", "user_rating": rating,
                   "problem_rating": pr}
        scored.append((score, {
            "contest_id": p["contestId"], "index": p["index"], "name": p["name"],
            "rating": pr, "tags": tags, "why": why, "score": score,
        }))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


def set_preference(db: Session, user_id: int, contest_id: int, index: str,
                   state: str) -> None:
    """Sets a later/dismissed/interested preference on a problem."""
    prob = db.query(Problem).filter_by(
        contest_id=contest_id, index=index, platform="codeforces").first()
    if prob is None:
        # The problem may not be in the catalog yet (never synced). Record
        # it bare so the preference still applies once it appears.
        prob = Problem(contest_id=contest_id, index=index, name="", rating=None,
                       tags=[], platform="codeforces")
        db.add(prob)
        db.flush()
    pref = db.query(ProblemPreference).filter_by(
        user_id=user_id, problem_id=prob.id).first()
    if pref is None:
        pref = ProblemPreference(user_id=user_id, problem_id=prob.id, state=state)
        db.add(pref)
    else:
        pref.state = state
    db.commit()


def list_preferences(db: Session, user_id: int) -> list[dict]:
    rows = (db.query(ProblemPreference, Problem)
            .join(Problem, ProblemPreference.problem_id == Problem.id)
            .filter(ProblemPreference.user_id == user_id)
            .order_by(ProblemPreference.updated_at.desc()).all())
    return [{
        "contest_id": p.contest_id, "index": p.index, "name": p.name,
        "rating": p.rating, "tags": p.tags or [], "state": pref.state,
    } for pref, p in rows]


def build_revision_queue(db: Session, user_id: int) -> None:
    """Seed the revision queue from history: problems solved after many wrong
    attempts, or attempted but never solved. Interval starts at 1 day."""
    per_problem: dict[int, dict] = defaultdict(lambda: {"wrong": 0, "solved": False})
    for sub in db.query(Submission).filter(Submission.user_id == user_id).all():
        p = per_problem[sub.problem_id]
        if sub.verdict == "OK":
            p["solved"] = True
        else:
            p["wrong"] += 1
    existing = {r.problem_id for r in db.query(Revision).filter(Revision.user_id == user_id).all()}
    now = datetime.utcnow()
    for pid, info in per_problem.items():
        if pid in existing:
            continue
        if (info["solved"] and info["wrong"] >= 3) or (not info["solved"] and info["wrong"] >= 2):
            db.add(Revision(
                user_id=user_id, problem_id=pid, interval_days=1, interval_step=0,
                due_date=now + timedelta(days=1), wrong_attempts=info["wrong"],
            ))
    db.commit()


def review_revision(db: Session, user_id: int, revision_id: int, result: str) -> Revision | None:
    """Again/Hard/Good/Easy — move the interval along [1,3,7,14,30] days.
    Again: back to 1 day. Hard: stay near the current interval. Good: next
    interval. Easy: advance two steps. The revision is rescheduled, never
    finished — when its next due date arrives it shows up as due again."""
    rev = db.query(Revision).filter(
        Revision.id == revision_id, Revision.user_id == user_id).first()
    if rev is None:
        return None
    step = rev.interval_step
    if result == "again":
        step = 0
    elif result == "hard":
        step = step  # same interval
    elif result == "good":
        step = min(step + 1, len(INTERVALS) - 1)
    elif result == "easy":
        step = min(step + 2, len(INTERVALS) - 1)
    else:
        return None
    rev.interval_step = step
    rev.interval_days = INTERVALS[step]
    rev.last_result = result
    rev.due_date = datetime.utcnow() + timedelta(days=INTERVALS[step])
    db.commit()
    return rev


def revision_list(db: Session, user_id: int, tab: str) -> list[dict]:
    now = datetime.utcnow()
    q = db.query(Revision, Problem).join(Problem, Revision.problem_id == Problem.id).filter(
        Revision.user_id == user_id)
    if tab == "due":
        q = q.filter(Revision.due_date <= now).order_by(Revision.due_date.asc())
    elif tab == "upcoming":
        q = q.filter(Revision.due_date > now).order_by(Revision.due_date.asc())
    else:  # done — reviewed at least once, most recently reviewed first
        q = q.filter(Revision.last_result.isnot(None)).order_by(
            Revision.updated_at.desc())
    rows = q.all()
    return [{
        "id": r.id,
        "problem": {"contest_id": p.contest_id, "index": p.index, "name": p.name,
                    "rating": p.rating, "tags": p.tags or []},
        "interval_days": r.interval_days,
        "due_date": r.due_date.isoformat(),
        "last_result": r.last_result,
        "wrong_attempts": r.wrong_attempts,
        "done": r.last_result is not None,
    } for r, p in rows]
