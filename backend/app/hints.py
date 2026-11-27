"""AI Hint Ladder — progressive hints via Gemini Flash (server-side only).

A stuck user unlocks hints one step at a time on a problem detail page:
step 1 nudge -> step 2 approach -> step 3 key insight. Never a full
solution, never code.

Design (specs/ai-hint-ladder/spec.md):
- Gemini is called through its REST API with httpx (no new dependency —
  same pattern as google_oauth). The key lives in the environment only;
  a missing key degrades to 503, never a startup crash.
- Hints are cached in the ai_hints table (unique per user/problem/step)
  so a repeat costs no Gemini call and no quota.
- Daily limit (HINT_DAILY_LIMIT, default 10/user/day, UTC) counts only
  new generations. The count lives in the DB so it survives restarts.
- The prompt is built from the problem (name/rating/tags) and the
  user's own attempts. The Codeforces API exposes no problem statement,
  so the prompt says that honestly and tells the model not to invent
  statement details.
"""
from datetime import datetime, timedelta

import httpx

from . import config
from .models import AiHint, HintUsage

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class HintNotConfigured(Exception):
    """GEMINI_API_KEY is not set — surfaced as 503."""


class HintError(Exception):
    """Gemini (or the network) failed — surfaced as 502, no detail leaked."""


class HintLimitReached(Exception):
    """Daily generation limit hit — surfaced as 429 with Retry-After."""

    def __init__(self, retry_after: int):
        super().__init__("Daily hint limit reached")
        self.retry_after = retry_after


def is_configured() -> bool:
    return bool(config.GEMINI_API_KEY)


_STEP_INSTRUCTIONS = {
    1: ("Step 1 — nudge: point at the single thing to notice first "
        "(an observation about the input, the constraints, or a small "
        "example). Do NOT name an algorithm or approach."),
    2: ("Step 2 — approach: name the strategy family to try (which "
        "technique area, what to think about structuring). Still no "
        "code, no pseudocode, no step-by-step solution."),
    3: ("Step 3 — key insight: the crux observation that unlocks the "
        "problem. Still no full solution, no code, no editorial link."),
}


def build_prompt(problem: dict, detail: dict, user_rating, step: int,
                 lang: str) -> str:
    """Builds the Gemini prompt for one ladder step.

    problem: {contest_id, index, name, rating, tags} (from the catalog
    or the public CF problemset fallback). detail: services.problem_detail
    output (attempts, wrong_attempts, submissions). user_rating may be None.
    """
    subs = detail.get("submissions") or []
    verdicts = ", ".join(
        f"{s['verdict']}({s['passed_test_count']} tests)"
        if s.get("passed_test_count") is not None else s["verdict"]
        for s in subs[:8])
    languages = ", ".join(sorted({s["language"] for s in subs if s.get("language")})) or "none yet"
    rating = problem.get("rating")
    tags = ", ".join(problem.get("tags") or []) or "none"
    language_name = "Bangla (Bangla script)" if lang == "bn" else "English"
    return (
        "You are a Codeforces practice coach. The user is stuck on a "
        "problem and wants a progressive hint — NOT the solution.\n\n"
        f"Problem: {problem.get('contest_id')}{problem.get('index')} — "
        f"{problem.get('name')} (rating {rating if rating else 'unrated'}, "
        f"tags: {tags}).\n"
        f"User rating: {user_rating if user_rating else 'unknown'}.\n"
        f"Attempts so far: {detail.get('attempts', 0)} "
        f"({detail.get('wrong_attempts', 0)} wrong). "
        f"Recent verdicts: {verdicts or 'no attempts yet'}. "
        f"Languages tried: {languages}.\n\n"
        "Note: the full problem statement is NOT available to you. Work "
        "from the problem name, rating, tags and the attempt history, plus "
        "your knowledge of this Codeforces problem. If you are unsure "
        "about the problem, say so briefly and give a hint for this "
        "problem type and rating instead of inventing statement details.\n\n"
        f"Give ONLY step {step} of 3:\n{_STEP_INSTRUCTIONS[step]}\n\n"
        "Rules: 2-4 sentences. Plain text only: no markdown headings, "
        "no LaTeX, no bullet lists. Never give the full solution. "
        "Never write code or pseudocode. Never link the editorial. "
        f"Respond in {language_name}."
    )


def _call_gemini(prompt: str) -> str:
    """One Gemini generateContent call. Raises HintError on any failure."""
    url = f"{GEMINI_BASE}/{config.GEMINI_MODEL}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        # thinkingBudget 0: hints are 2-4 sentences and need no
        # reasoning trace — without this, thinking tokens eat the
        # output budget and the visible hint comes back truncated
        # (verified live 2026-11-28: empty/truncated replies).
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 400,
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
        raise HintError(f"Gemini request failed: {type(exc).__name__}") from exc
    if resp.status_code != 200:
        raise HintError(f"Gemini HTTP {resp.status_code}")
    try:
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, AttributeError, ValueError) as exc:
        raise HintError("Gemini response was unparsable") from exc
    if not text:
        raise HintError("Gemini returned an empty hint")
    return text


def _today_start_utc() -> datetime:
    now = datetime.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def used_today(db, user_id: int) -> int:
    """Generations (new hints, not cache hits) by this user today (UTC).

    Counts HintUsage rows: a language regeneration updates the AiHint
    row in place, so counting AiHint rows would under-count.
    """
    return db.query(HintUsage).filter(
        HintUsage.user_id == user_id,
        HintUsage.created_at >= _today_start_utc()).count()


def _record_generation(db, user_id: int) -> None:
    db.add(HintUsage(user_id=user_id))


def seconds_to_midnight_utc() -> int:
    now = datetime.utcnow()
    midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((midnight - now).total_seconds()))


def unlocked_steps(db, user_id: int, problem_id: int) -> list[int]:
    """Steps already unlocked for this user+problem (any language)."""
    rows = db.query(AiHint.step).filter(
        AiHint.user_id == user_id, AiHint.problem_id == problem_id).all()
    return sorted({r[0] for r in rows})


def get_hints(db, user_id: int, problem_id: int) -> list[AiHint]:
    return (db.query(AiHint)
            .filter(AiHint.user_id == user_id, AiHint.problem_id == problem_id)
            .order_by(AiHint.step).all())


def unlock_hint(db, user, problem: dict, problem_id: int, detail: dict,
                step: int, lang: str) -> tuple[str, bool]:
    """Unlocks one ladder step. Returns (text, cached).

    Raises ValueError (400: bad step / out of order / already solved),
    HintNotConfigured (503), HintLimitReached (429), HintError (502).
    The daily limit counts only new generations — cache hits are free.
    """
    if step not in (1, 2, 3):
        raise ValueError("step must be 1, 2 or 3")
    if detail.get("solved"):
        raise ValueError("Problem already solved — hints are for stuck problems")
    unlocked = unlocked_steps(db, user.id, problem_id)
    if step > 1 and (step - 1) not in unlocked:
        raise ValueError(f"Unlock step {step - 1} first")
    existing = (db.query(AiHint)
                .filter_by(user_id=user.id, problem_id=problem_id, step=step)
                .first())
    if existing is not None and existing.lang == lang:
        return existing.text, True
    if not is_configured():
        raise HintNotConfigured()
    if used_today(db, user.id) >= config.HINT_DAILY_LIMIT:
        raise HintLimitReached(seconds_to_midnight_utc())
    text = _call_gemini(build_prompt(
        problem, detail, user.current_rating, step, lang))
    _record_generation(db, user.id)
    if existing is not None:
        # Language switch: regenerate this step in the new language.
        existing.text = text
        existing.lang = lang
    else:
        db.add(AiHint(user_id=user.id, problem_id=problem_id, step=step,
                      lang=lang, text=text))
    db.commit()
    return text, False
