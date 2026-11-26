"""Analytics: weak topics, recommendations, streak, heatmap.

Weak-topic rule (from the plan, numeric): a tag counts as weak only with
enough attempts (>= 5) AND low acceptance (< 50%) OR many wrong attempts
on average (>= 2 per attempted problem). 1–2 attempts never label a tag weak.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from .models import Problem, ProblemFeedback, Revision, Submission, User

INTERVALS = [1, 3, 7, 14, 30]
MIN_ATTEMPTS_FOR_WEAK = 5
WEAK_ACCEPTANCE = 0.50
WEAK_AVG_WRONG = 2.0


def _problem_key(p: Problem) -> str:
    return f"{p.contest_id}{p.index}"


def tag_stats(db: Session, user_id: int) -> list[dict]:
    """Per-tag: attempted, solved, acceptance %, avg wrong attempts, last solve."""
    subs = (
        db.query(Submission, Problem)
        .join(Problem, Submission.problem_id == Problem.id)
        .filter(Submission.user_id == user_id)
        .all()
    )
    per_tag: dict[str, dict] = defaultdict(
        lambda: {"tag": "", "attempted": 0, "solved": 0, "wrong": 0,
                 "solved_problems": set(), "attempted_problems": set(), "last_solve": None}
    )
    for sub, prob in subs:
        for tag in prob.tags or []:
            s = per_tag[tag]
            s["tag"] = tag
            s["attempted_problems"].add(prob.id)
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
        weak = attempted >= MIN_ATTEMPTS_FOR_WEAK and (
            acceptance < WEAK_ACCEPTANCE or avg_wrong >= WEAK_AVG_WRONG
        )
        out.append({
            "tag": tag,
            "attempted": attempted,
            "solved": solved,
            "acceptance": round(acceptance, 2),
            "avg_wrong_attempts": round(avg_wrong, 1),
            "last_solve": s["last_solve"].isoformat() if s["last_solve"] else None,
            "weak": weak,
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
    """Rule-based recommendations: near the user's rating (+0..+200 band),
    weak tags first, unsolved, each with a one-line 'why'."""
    solved = solved_problem_ids(db, user.id) if hide_solved else set()
    solved_keys = set()
    if solved:
        for p in db.query(Problem).filter(Problem.id.in_(solved)).all():
            solved_keys.add((p.contest_id, p.index))
    weak = {t["tag"]: t for t in weak_tags(db, user.id)}
    rating = user.current_rating or 1200
    lo = min_rating if min_rating is not None else rating
    hi = max_rating if max_rating is not None else rating + 200
    dismissed = {
        (f.contest_id, f.problem_index)
        for f in db.query(ProblemFeedback).filter(
            ProblemFeedback.user_id == user.id,
            ProblemFeedback.action == "not_interested").all()
    }
    scored = []
    for p in problems:
        pr = p.get("rating")
        if pr is None or pr < lo or pr > hi:
            continue
        key = (p["contestId"], p["index"])
        if key in solved_keys or key in dismissed:
            continue
        tags = p.get("tags", [])
        if tag and tag not in tags:
            continue
        weak_hit = [t for t in tags if t in weak]
        # Weak-tag problems first, then closest to the user's rating.
        score = (len(weak_hit) > 0, -abs(pr - rating))
        # Structured "why" — the frontend renders the sentence in the
        # active locale (EN/BN). Never build a sentence here.
        if weak_hit:
            w = weak[weak_hit[0]]
            if w["acceptance"] < WEAK_ACCEPTANCE:
                why = {"kind": "weak_acceptance", "tag": weak_hit[0],
                       "acceptance": int(w["acceptance"] * 100),
                       "problem_rating": pr, "user_rating": rating}
            else:
                why = {"kind": "weak_wrong", "tag": weak_hit[0],
                       "avg_wrong_attempts": w["avg_wrong_attempts"],
                       "problem_rating": pr, "user_rating": rating}
        else:
            why = {"kind": "near_rating", "user_rating": rating,
                   "problem_rating": pr}
        scored.append((score, {
            "contest_id": p["contestId"], "index": p["index"], "name": p["name"],
            "rating": pr, "tags": tags, "why": why,
        }))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


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
    """Again/Hard/Good/Easy — move the interval along [1,3,7,14,30] days."""
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
    rev.done = True
    db.commit()
    return rev


def revision_list(db: Session, user_id: int, tab: str) -> list[dict]:
    now = datetime.utcnow()
    q = db.query(Revision, Problem).join(Problem, Revision.problem_id == Problem.id).filter(
        Revision.user_id == user_id)
    if tab == "due":
        q = q.filter(Revision.due_date <= now, Revision.done == False)  # noqa: E712
    elif tab == "upcoming":
        q = q.filter(Revision.due_date > now, Revision.done == False)  # noqa: E712
    else:  # done
        q = q.filter(Revision.done == True)  # noqa: E712
    rows = q.order_by(Revision.due_date.asc()).all()
    return [{
        "id": r.id,
        "problem": {"contest_id": p.contest_id, "index": p.index, "name": p.name,
                    "rating": p.rating, "tags": p.tags or []},
        "interval_days": r.interval_days,
        "due_date": r.due_date.isoformat(),
        "last_result": r.last_result,
        "wrong_attempts": r.wrong_attempts,
        "done": r.done,
    } for r, p in rows]
