# AI Hint Ladder — spec

## Goal

A stuck user gets progressive help on a problem detail page: 3 steps —
**1 nudge → 2 approach → 3 key insight** — generated server-side by
Gemini Flash from the problem (name, rating, tags) and the user's own
attempts. Never a full solution, never code.

Approved by Khalid 2026-11-28 00:44 ("shob add koro"). His #1 AI pick:
Codeforces itself does not offer this.

## Non-goals (explicit)

- NO full-solution generator (kills learning — explicitly rejected).
- NO chatbot page (scope creep — explicitly rejected).
- NO rating predictor (too little real data — explicitly rejected).
- NO BYOK: end users never set up their own API key. AI runs on
  Khalid's server-side Gemini key, per-user rate-limited, with graceful
  degradation.

## API (backend, all under /api/v1, JWT required)

- `GET /problems/{contest_id}/{index}/hints`
  Returns `{configured, hints: [{step, text, lang}], used_today, limit}` —
  the steps already unlocked for this problem.
- `POST /problems/{contest_id}/{index}/hints` body
  `{step: 1|2|3, lang?: "en"|"bn"}` — unlocks one step.
  Returns `{step, text, cached, used_today, limit}`.

Rules:
- Steps unlock in order: step 2 requires step 1 unlocked, step 3
  requires step 2. Out-of-order → 400.
- step outside 1..3 → 400 (422 via validation is fine too).
- Problem must resolve (local catalog, else the public CF problemset
  fallback — same as the detail endpoint; the problem row is created
  locally first so the hint has a problem to attach to). Unknown
  problem → 404.
- Solved problem → 400 ("already solved — hints are for stuck
  problems"). The frontend hides the button when solved.
- No attempts yet is allowed — the prompt says so.

## Data model (new table `ai_hints`, migration 0006)

- `id`, `user_id` FK users CASCADE, `problem_id` FK problems CASCADE,
  `step` 1..3, `lang` ("en"/"bn"), `text`, `created_at`.
- `hint_usage`: one row per generation (`user_id`, `created_at`) — the
  daily-limit counter (see Rate limit).
- Unique `(user_id, problem_id, step)` — the cache key. The generated
  language is recorded; switching UI language regenerates that step
  in the new language (counts against the daily limit).
- A cache hit returns the stored text: no Gemini call, no quota use.

## Rate limit (per user, per UTC day)

- `HINT_DAILY_LIMIT` (env, default **10** generations/user/day).
  A full ladder (3 steps) for 3 problems a day, plus one spare.
  Cache hits do not count. Count = `hint_usage` rows created today (UTC) — one row per generation, because a language regeneration updates the `ai_hints` row in place and would otherwise under-count.
- Over limit → 429 with `Retry-After` seconds to midnight UTC.
- Single-worker in-memory limits are NOT used here: the count lives in
  the DB, so it survives restarts (same reason the sync queue is
  DB-backed).

## Gemini integration (new module `backend/app/hints.py`)

- REST via `httpx` (no new dependency — same pattern as google_oauth):
  `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
  with `x-goog-api-key` header, 30 s timeout.
- Config (read lazily, `backend/app/config.py`):
  `GEMINI_API_KEY` (empty → 503 "AI hints are not configured yet"),
  `GEMINI_MODEL` (default `gemini-3.5-flash`),
  `HINT_DAILY_LIMIT` (default 10), `HINT_HTTP_TIMEOUT_S` (default 30).
  Names only in `.env.example`.
- Prompt input: contest_id + index, name, rating, tags, user rating,
  attempts (verdicts, passed-test counts, languages, count).
  Honest limit, stated in the prompt: the Codeforces API exposes no
  problem statement, so the model works from name/rating/tags/attempts
  and its knowledge of the problem — it must say so if it is unsure,
  never invent statement details.
- Model, verified live 2026-11-28 against the real key: gemini-2.5-flash
  404s for this key ("no longer available to new users");
  gemini-3.8-flash hangs on generateContent (>90 s, every prompt);
  gemini-3.5-flash answers in ~1.5 s. generationConfig sets
  thinkingBudget 0 — without it, thinking tokens eat the output
  budget and hints come back empty/truncated.
- Prompt rules (tested): short (2–4 sentences); step 1 = what to
  notice (nudge, no approach); step 2 = approach/strategy family
  (still no code); step 3 = the crux insight (still no full solution,
  no code, no editorial link). Response in the requested language.
- Failures: Gemini error / timeout / unparsable response → 502
  "hint service unavailable — try again later" (no detail leaked).

## Frontend (Problem Detail page only)

- New "AI hints" card between Submissions and Notes (glass/teal,
  existing design tokens). Three step buttons (1/2/3); locked steps
  are disabled until the previous one is unlocked; unlocked hints
  render as plain text; usage line "X / 10 hints used today";
  loading spinner while generating; errors shown inline.
- Demo mode: card shows a note that hints need sign-in; button
  disabled. Solved problem: button hidden with a "already solved" note.
- `api/client.ts`: `getHints(cid, idx)`, `requestHint(cid, idx, step,
  lang)`; `api/types.ts`: `HintStep`, `HintsResponse`.
- i18n (dict.ts + en.ts + bn.ts): hintTitle, hintStepN labels,
  hintGet, hintUsedToday(n, limit), hintNotConfigured,
  hintUnavailable, hintLimitReached, hintDemoNote, hintSolvedNote,
  hintStepLocked.

## Tests (`backend/tests/test_hints.py`, Gemini mocked — no network)

- 503 when the key is not configured.
- Happy path step 1 (mocked Gemini) + step 2 after step 1.
- Out-of-order step → 400; step 0/4 → 400/422; unknown problem → 404;
  solved problem → 400.
- Cache: second request for the same step makes NO second Gemini call
  and does not consume quota.
- Daily limit: with `HINT_DAILY_LIMIT=2`, third generation → 429.
- Gemini failure → 502.
- Prompt guardrail: the built prompt contains the no-code /
  no-full-solution instructions (unit test on the prompt builder).
- Auth required (401 without a token).

## Verification checklist

- pytest: full suite green except the 2 pre-existing UTC flakes
  (00:00–06:00 Dhaka only).
- Frontend build: `tsc -b && vite build` passes.
- Dev backend restarted; hint endpoint proven locally — real Gemini
  call if the laptop .env has a key, otherwise mocked (state which).
- Commit (one) + push via askpass; Render redeploy; live health 200,
  /docs 404, hint endpoint behaviour reported honestly (200 with a
  hint, or the pending-config state if the key is missing on Render).
