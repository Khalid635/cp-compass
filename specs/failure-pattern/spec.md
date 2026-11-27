# Spec — Batch 2: Failure-pattern analysis

## Goal

Show the user WHERE their solutions fail, using data Codeforces already
returns: each submission carries a `passedTestCount` (how many tests
passed before the verdict) and a verdict (OK / WRONG_ANSWER /
TIME_LIMIT_EXCEEDED / MEMORY_LIMIT_EXCEEDED / RUNTIME_ERROR /
COMPILATION_ERROR). No new Codeforces fields are needed.

## Data reality (checked 2026-11-27, dev DB)

The real user (khalidmasud22@gmail.com) has 16 submissions: 10 OK,
4 WRONG_ANSWER, 1 RUNTIME_ERROR, 1 COMPILATION_ERROR. 11 distinct
problems, 10 solved. Most wrong attempts: Watermelon (4A) — 3 wrong
before AC. Everything else is 1 wrong at most. **Thin data is the
normal case here**: the UI must show the real numbers and say plainly
when there is too little data for a pattern. Never hide the counts,
never invent a diagnosis.

## Backend

1. `Submission.passed_test_count` (Integer, nullable) + Alembic
   migration `0004_passed_test_count`. The sync upsert stores
   `s.get("passedTestCount")` for every new submission.
2. Backfill: at the end of `run_sync`, if any of the user's rows have
   `passed_test_count IS NULL`, fetch `user.status` pages (max 5 pages
   per run) and fill them. Bounded, self-healing, zero extra CF calls
   once all rows are filled.
3. `services.failure_patterns(db, user_id)` — pure computation over the
   user's submissions joined with problems. Shared core
   `_compute_failure_patterns(rows)` also used by the demo seed, so
   demo and real data can never drift apart.
   - `verdict_breakdown`: count per verdict (all verdicts, OK included).
   - `test_stages`: non-OK submissions with known test counts, bucketed
     by tests passed — early (0–2), middle (3–9), late (10+); plus
     `unknown` for NULL test counts. Buckets are documented thresholds,
     not a claim about any specific problem's test count.
   - `per_topic`: per tag — wrong count, verdict split, median tests
     passed, early-fail share, and a `signal`: `early` (wrong >= 3 and
     early share >= 0.6), `late` (wrong >= 3 and late share >= 0.6),
     `mixed` (wrong >= 3, neither dominates), `thin` (wrong < 3 —
     counts shown, no pattern claimed).
   - `per_problem`: problems with >= 1 wrong attempt, most wrong first
     (top 8): wrong count, verdicts, passed test counts, solved flag,
     first/last attempt.
   - `wrong_before_first_ac`: for solved problems, wrong submissions
     before the first OK — buckets 0 / 1–2 / 3+ and the median.
   - `coverage`: total submissions, with/without test data.
     `enough_data` is true when `total_wrong >= 3`.
4. Endpoints: `GET /api/v1/analytics/failures` (auth) and
   `GET /api/v1/demo/analytics/failures` (demo seed, same shape).
5. `services.problem_detail` submissions now include
   `passed_test_count` so the Problem Detail table can show it.

## Frontend

- Analytics: a "Failure patterns" card (after the difficulty-success
  table). Verdict breakdown, test-stage distribution, per-topic rows
  (thin ones labelled as too little data), top per-problem list.
  Empty state when `total_wrong == 0`; low-data note when not
  `enough_data`. Every number labelled with its base
  ("based on 6 of 16 submissions").
- Problem Detail: a "Tests" column in the submissions table
  ("passed N tests" / "—" when unknown) + a one-line summary in the
  attempts card when wrong attempts >= 2 and test data exists.
- All copy in EN + BN (`en.ts` / `bn.ts` + `dict.ts`). Copy rules:
  report what was observed ("most failures happened on early tests"),
  hedge the interpretation ("which often means an edge case or a
  misread statement"), never state a diagnosis as fact.

## Verification

- `pytest` green (new `tests/test_failure_patterns.py`: verdict
  breakdown, stage bucketing incl. NULL handling, signal thresholds,
  thin-data flags, backfill stores the count, problem_detail carries
  the count).
- Frontend `npm run build` passes.
- Live smoke on the dev stack: real endpoint returns the real user's
  patterns (16 subs); demo endpoint returns demo patterns; Analytics
  demo page + a real problem page render; desktop + mobile screenshots.

## Out of scope

Backtest (Batch 3), contest post-mortem (Batch 4), SSE/PWA/public
profile/friend compare/.ics (Batch 5). No new Codeforces calls beyond
the bounded backfill. No ML changes.
