"""Contest post-mortem AI - Gemini-written analysis of a post-mortem
report (server-side only, batch 4).

The analysis is generated once per user+contest and cached in the
postmortem_analysis table; a repeat (same language) costs no Gemini
call and no quota. A language switch regenerates the row in place
and counts against the daily limit, like the Hint Ladder.

Design (specs/batch4/spec.md) - mirrors hints.py:
- Gemini is called through its REST API with httpx (no new
  dependency). The key lives in the environment only; a missing key
  degrades to 503, never a startup crash.
- Daily limit (POSTMORTEM_DAILY_LIMIT, default 5/user/day, UTC)
  counts only new generations. The count lives in the DB so it
  survives restarts.
- The prompt is built from the deterministic post-mortem report
  (counts, verdicts, per-problem rows, weak topics) plus the user's
  global failure-patterns summary. Analysis only: strengths,
  mistakes, what to practice next week. Never a full solution,
  never code, never an editorial link.
"""
from datetime import datetime, timedelta

import httpx

from . import config
from .models import PostmortemAnalysis, PostmortemUsage

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class PostmortemNotConfigured(Exception):
    """GEMINI_API_KEY is not set - surfaced as 503."""


class PostmortemError(Exception):
    """Gemini (or the network) failed - surfaced as 502, no detail leaked."""


class PostmortemLimitReached(Exception):
    """Daily generation limit hit - surfaced as 429 with Retry-After."""

    def __init__(self, retry_after: int):
        super().__init__("Daily post-mortem analysis limit reached")
        self.retry_after = retry_after


def is_configured() -> bool:
    return bool(config.GEMINI_API_KEY)


def build_prompt(report: dict, failure_summary: dict | None,
                 user_rating, lang: str) -> str:
    """Builds the Gemini prompt for one contest post-mortem analysis.

    report: services._compute_postmortem output. failure_summary: the
    global failure-patterns payload (or None when there is not enough
    data for one). user_rating may be None.
    """
    nl = chr(10)
    name = report.get("contest_name") or f"contest {report['contest_id']}"
    per_problem = []
    for row in report.get("per_problem") or []:
        p = row["problem"]
        minutes = row.get("minutes_to_solve")
        solved_part = (f"solved, {minutes} min to solve"
                       if minutes is not None else "unsolved")
        per_problem.append(
            f"{p['index']} {p.get('name')} (rating {p.get('rating') or 'unrated'}, "
            f"tags: {', '.join(p.get('tags') or []) or 'none'}): "
            f"{row['attempts']} attempt(s), {row['wrong_attempts']} wrong, "
            f"{solved_part}")
    verdicts = ", ".join(
        f"{v['verdict']} x{v['count']}"
        for v in report.get("verdict_breakdown") or [])
    weak = ", ".join(
        f"{t['tag']} ({t['solved']}/{t['attempted']} solved)"
        for t in report.get("weak_topics") or []) or "none"
    topics = ", ".join(
        (report.get("practice_next_week") or {}).get("topics") or []) or "none"
    summary = ""
    if failure_summary:
        summary = (
            f"Global pattern (all contests): "
            f"{failure_summary.get('total_wrong', 0)} wrong submissions, "
            f"{failure_summary.get('total_submissions', 0)} total. "
            f"Top weak topics: "
            + ", ".join(
                f"{t['tag']} ({t['signal']})"
                for t in (failure_summary.get("per_topic") or [])[:3]
            )
            + ". "
        )
    language_name = "Bangla (Bangla script)" if lang == "bn" else "English"
    spent = report.get("time_spent_minutes")
    time_line = f" Time spent: {spent} minutes." if spent is not None else ""
    lines = [
        "You are a Codeforces practice coach. The user finished a "
        "contest and wants a written post-mortem - an analysis of how "
        "they did, what went wrong, and what to practice next week. "
        "This is analysis, NOT solutions. Never give a full solution. "
        "Never write code or pseudocode. Never link the editorial.",
        "",
        f"Contest: {name} (id {report['contest_id']}).",
        f"User rating: {user_rating if user_rating else 'unknown'}.",
        f"Solved {report.get('solved', 0)} of {report.get('attempted', 0)} "
        f"attempted problems, {report.get('total_submissions', 0)} "
        f"submissions total.{time_line}",
        f"Verdicts: {verdicts or 'none'}.",
        "Per problem:",
        *per_problem,
        f"Weak topics this contest: {weak}.",
        f"Suggested practice topics: {topics}.",
        summary,
        "Note: the full problem statements are NOT available to you. "
        "Work from the problem names, ratings, tags and the attempt "
        "history, plus your knowledge of these Codeforces problems. If "
        "you are unsure about a problem, say so briefly and analyse "
        "the pattern instead of inventing statement details.",
        "",
        "Write the post-mortem in 6-10 sentences, plain text only: no "
        "markdown headings, no LaTeX, no bullet lists. Cover: (1) what "
        "went well, (2) the clearest mistake pattern, (3) what to "
        "practice next week. "
        f"Respond in {language_name}.",
    ]
    return nl.join(lines)


def _call_gemini(prompt: str) -> str:
    """One Gemini generateContent call. Raises PostmortemError on failure."""
    url = f"{GEMINI_BASE}/{config.GEMINI_MODEL}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        # thinkingBudget 0: a 6-10 sentence analysis needs no reasoning
        # trace - without this, thinking tokens eat the output budget
        # and the visible text comes back truncated (verified live
        # 2026-11-28 on the Hint Ladder: empty/truncated replies).
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800,
                             "thinkingConfig": {"thinkingBudget": 0}},
    }
    headers = {
        "x-goog-api-key": config.GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=config.HINT_HTTP_TIMEOUT_S) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise PostmortemError(f"Gemini request failed: {type(exc).__name__}") from exc
    if resp.status_code != 200:
        raise PostmortemError(f"Gemini HTTP {resp.status_code}")
    try:
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, AttributeError, ValueError) as exc:
        raise PostmortemError("Gemini response was unparsable") from exc
    if not text:
        raise PostmortemError("Gemini returned an empty analysis")
    return text


def _today_start_utc() -> datetime:
    now = datetime.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def used_today(db, user_id: int) -> int:
    """Generations (new analyses, not cache hits) by this user today (UTC).

    Counts PostmortemUsage rows: a language regeneration updates the
    PostmortemAnalysis row in place, so counting PostmortemAnalysis
    rows would under-count.
    """
    return db.query(PostmortemUsage).filter(
        PostmortemUsage.user_id == user_id,
        PostmortemUsage.created_at >= _today_start_utc()).count()


def _record_generation(db, user_id: int, contest_id: int) -> None:
    db.add(PostmortemUsage(user_id=user_id, contest_id=contest_id))


def seconds_to_midnight_utc() -> int:
    now = datetime.utcnow()
    midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((midnight - now).total_seconds()))


def get_analysis(db, user_id: int, contest_id: int) -> PostmortemAnalysis | None:
    return (db.query(PostmortemAnalysis)
            .filter_by(user_id=user_id, contest_id=contest_id)
            .first())


def generate_analysis(db, user, report: dict, failure_summary: dict | None,
                      lang: str) -> tuple[str, bool]:
    """Generates (or returns the cached) analysis for one contest.

    Returns (text, cached). Raises ValueError (400: no data),
    PostmortemNotConfigured (503), PostmortemLimitReached (429),
    PostmortemError (502). The daily limit counts only new
    generations - cache hits are free.
    """
    if not report.get("has_data"):
        raise ValueError("No submissions for this contest - nothing to analyse")
    existing = get_analysis(db, user.id, report["contest_id"])
    if existing is not None and existing.lang == lang:
        return existing.text, True
    if not is_configured():
        raise PostmortemNotConfigured()
    if used_today(db, user.id) >= config.POSTMORTEM_DAILY_LIMIT:
        raise PostmortemLimitReached(seconds_to_midnight_utc())
    text = _call_gemini(build_prompt(
        report, failure_summary, user.current_rating, lang))
    _record_generation(db, user.id, report["contest_id"])
    if existing is not None:
        # Language switch: regenerate this contest's analysis in the
        # new language.
        existing.text = text
        existing.lang = lang
        existing.model = config.GEMINI_MODEL
    else:
        db.add(PostmortemAnalysis(user_id=user.id,
                                  contest_id=report["contest_id"],
                                  lang=lang, text=text,
                                  model=config.GEMINI_MODEL))
    db.commit()
    return text, False
