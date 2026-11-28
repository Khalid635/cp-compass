# Spec — Batch 4: Contest post-mortem (full report + AI analysis)

## Status: new feature, spec-first (approved 2026-11-28 00:44, "shob add koro")

Two approved AI features, built together because the AI analysis reads
the deterministic report: (1) contest post-mortem full report — after a
contest, auto-analysis of performance: time spent, mistakes, what to
practice next week; (2) contest post-mortem AI — Gemini-written analysis
of that report. Pairs with the mistake-pattern mining data (af935a3)
and the Batch 3 backtest numbers (README methodology).

## Data honesty — verified 2026-11-28 ~09:35, before any change

- Khalid did NOT play Codeforces Round 1138 (Div. 3, contest 2292,
  27 Nov 20:35-22:50). Verified twice: dev DB has 16 submissions,
  latest 2026-10-26; CF API user.status agrees (latest 2026-10-26
  07:36, contest 1374). No submissions on 27 Nov at all.
- His real contests with submissions (11 contests, 16 submissions):
  4, 20, 25, 50, 71, 158, 231, 1374, 1703, 1729, 1974. Densest
  session: 2026-07-23, 8 submissions across contests 4/231/50/71.
- Live Neon has 0 submissions (mining spec) — post-mortem on live
  shows empty states until he connects his handle and syncs on live.
- Consequence: the post-mortem is PER-CONTEST with an honest
  `has_data: false` empty state. NEVER fabricate a Round 1138
  report, score, or solved count. The "latest contest" is the most
  recent contest WITH submissions, never the most recent CF round.

## 1. Deterministic report (no LLM)

`services._compute_postmortem(rows, contest_id, contest_name)` — pure
function over row dicts `{verdict, passed_test_count, problem:
{contest_id, index, name, rating, tags}, submitted_at}`. Same shared-
computation pattern as `_compute_failure_patterns`, so the demo
endpoint runs the same code over seed.SUBMISSIONS.

Payload:
- `contest_id`, `contest_name` (null when unknown), `has_data`
- `attempted` (unique problems), `solved` (unique), `total_submissions`
- `verdict_breakdown`: [{verdict, count}]
- `first_submission`, `last_submission` (ISO), `time_spent_minutes`
  (last minus first; null when fewer than 2 submissions)
- `per_problem`: [{problem, attempts, wrong_attempts, solved,
  first_attempt, last_attempt, minutes_to_solve (first AC minus
  first attempt; null if unsolved), verdicts[]}] sorted by index
- `unsolved`: problem refs attempted but never AC
- `weak_topics`: tags with acceptance < 0.5 in this contest, min 2
  attempts (mirrors contest_analysis weak_tags_that_day)
- `practice_next_week`: {topics (weak topics + tags of unsolved
  problems, top 3), problems (unsolved refs)}

`services.postmortem(db, user_id, contest_id)` loads the user's
submissions for the contest (join problems) and calls the computation.
`services.postmortem_list(db, user_id)` returns contests with >= 1
submission: {contest_id, contest_name, attempted, solved,
submissions, first_activity, last_activity}, sorted by last_activity
desc. Contest names come from `cf.contest_list()` (new, cached 1h
like `problemset()`); names are display-only — CF down means
contest_name null, never a 500.

## 2. Endpoints (main.py)

- `GET /api/v1/postmortems` — list. 400 if no handle connected.
- `GET /api/v1/postmortems/latest` — most recent contest with
  submissions. 404 "No contest submissions yet" when none.
- `GET /api/v1/postmortems/{contest_id}` — 404 only when the contest
  is unknown to CF (validated via the cached contest list; CF down
  -> 502). A known contest with no user submissions -> 200 with
  `has_data: false` and zeroed counts (the honest Round 1138 path).
- `GET /api/v1/postmortems/{contest_id}/analysis` — cached analysis
  or {analysis: null, configured, used_today, limit}.
- `POST /api/v1/postmortems/{contest_id}/analysis` {lang} — generate.
  400 no post-mortem data; 503 Gemini not configured; 429 daily
  limit (5/user/day UTC, Retry-After to midnight UTC); 502 Gemini
  failure. Cache hits are free (no new generation, no quota).
- Demo (no auth, read-only): `GET /api/v1/demo/postmortems`,
  `/demo/postmortems/latest`, `/demo/postmortems/{contest_id}` — same
  computation over seed data; unknown contest -> 404; known contest
  with no demo submissions -> has_data false. NO demo AI endpoint —
  the demo page shows the sign-in note (hintDemoNote pattern).

## 3. AI analysis (app/postmortem_ai.py, mirrors hints.py)

- `PostmortemAnalysis` table: user_id, contest_id, lang, text,
  model, created_at; unique (user_id, contest_id). A language switch
  regenerates in place and counts against the daily limit (same as
  hints). `PostmortemUsage` table: one row per generation (the daily
  limit counts generations, not cached rows). Migration 0007.
- Model `config.GEMINI_MODEL` (gemini-3.5-flash; 2.5-flash 404s for
  this key, 3.8-flash hangs >90s — verified 2026-11-28).
  `thinkingConfig: {thinkingBudget: 0}` required or output comes
  back empty/truncated. temperature 0.7, maxOutputTokens 800.
- `POSTMORTEM_DAILY_LIMIT` (default 5, env-overridable) in config.py.
  Reuses `HINT_HTTP_TIMEOUT_S` (30s) and the GEMINI_API_KEY.
- Prompt: deterministic report numbers + per-problem rows + the
  global failure-patterns summary (verdict/stage/topic signals) +
  user rating. Guardrails: analysis ONLY — strengths, mistakes, what
  to practice next week. Never full solutions, never code or
  pseudocode, never editorial links. Plain text, ~6-10 sentences.
  Responds in the requested language (en/bn).

## 4. Frontend

- `Postmortems.tsx` (list) + `Postmortem.tsx` (detail), routes
  `/app/postmortems`, `/app/postmortems/:contestId` and the same
  under `/demo` (both take the `demo` prop like other pages).
- Detail sections: header (contest name/id, date range), summary
  stats (solved/attempted, time spent, verdict chips), per-problem
  table, unsolved + practice-next-week card, AI analysis card
  (generate button, "X / 5 analyses used today", errors mapped by
  status, demo sign-in note).
- Empty states: has_data false -> "No submissions for this contest
  yet" + sync hint; empty list -> "No contests yet" state.
- Nav item in layout.tsx (below Weekly report). i18n EN+BN for all
  new copy. api types + client methods (real + demo).

## Out of scope

- No sync on live; no Round 1138 report (no data exists).
- No rating-change display: rating history lives in
  contest_analysis; most of his contests are unrated practice —
  never present practice as a rated contest.
- No change to failure_patterns, weekly_report, hints, or the
  shipped model/split. No full-solution generation, no chatbot,
  no rating predictor changes.

## Verification

- tests/test_postmortem.py: computation unit tests (counts, verdicts,
  time spent, per-problem rows, unsolved, weak topics, empty state),
  endpoint tests (auth, list order, latest, detail 200 has_data
  false for a known contest with no subs, unknown contest 404,
  demo endpoints), AI tests with mocked Gemini (generate + cache,
  limit 429, missing key 503, no-data 400, prompt guardrails).
- Full pytest green except the 2 pre-existing UTC flakes
  (test_10/test_11, fail only 00:00-06:00 Dhaka).
- `npm run build` passes. Dev backend restarted (migration
  0006 -> 0007 at boot); real endpoints against Khalid's dev data
  (contest 231: 2 subs, 1 solved; contest 4: 4 subs, 1 solved) +
  demo endpoints; AI proven with real Gemini on the dev backend
  (throwaway scratch user, deleted afterwards; if the dev key is
  absent, mocked tests + live-503 honesty stand and the real-Gemini
  proof is marked unverified, not faked).
- Live after deploy: health 200, /docs 404, demo postmortems 200,
  real endpoints 401 without auth, DB-backed probe with a throwaway
  +alias account (deleted afterwards; live users back to 1).
