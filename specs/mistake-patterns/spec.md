# Spec — Mistake-pattern mining (Batch 3 follow-up)

## Status: core already exists — verify, then close the real gaps

Batch 2 (commit a1cea7f, "failure-pattern analysis") already built exactly
what "mistake-pattern mining" asked for: `services.failure_patterns` +
`_compute_failure_patterns` (verdict breakdown, early/middle/late test
stages, per-topic signals with a `thin` flag, per-problem top 8,
wrong-before-first-AC), endpoints `GET /api/v1/analytics/failures` +
`GET /api/v1/demo/analytics/failures`, and the Analytics "Failure
patterns" card (EN + BN). Rebuilding it would duplicate Batch 2.

Verified this batch (2026-11-28, before any change):
- Full pytest: 69 passed + 2 pre-existing UTC flakes (test_10/11).
- Dev backend :8004 demo endpoint: 355 subs, 143 wrong, all with test
  data; verdicts OK 212 / WA 56 / TLE 45 / RE 42; stages early 88 /
  middle 31 / late 24; top topics dp 53 mixed, graphs 38 mixed,
  greedy 22 early.
- Dev real endpoint (Khalid's dev account, TestClient + real token):
  16 subs, 6 wrong, all 16 with test data; verdicts OK 10 / WA 4 /
  CE 1 / RE 1; stages early 6; topics brute force 4 early, math 3
  early, graphs/dsu/greedy thin; top problem 4A Watermelon, 3 wrong,
  solved. `enough_data` true.
- Live (Render): health 200, /docs 404, real endpoint 401 without
  auth, demo endpoint 200 with the demo payload.
- Live Neon (read-only): alembic 0006, users 1 (verified), BUT
  **submissions 0, problems 0, cf_accounts 0, sync_jobs 0** — his
  Codeforces handle was never connected on live and no sync ever ran
  there. The 16 submissions exist only in the dev SQLite DB. On live
  the card will show the no-data state until he connects his handle
  and syncs on the live site (needs his live login — not this batch).

## Gaps this batch closes

1. **Recency window (named in the brief, missing from the payload).**
   The payload has per-problem first/last attempt but no windowed
   aggregate. Add a `recent` block: last 30 days (same 30-day
   convention as the weak-score recent acceptance in seed.py):
   `{"window_days": 30, "total_wrong": n, "verdict_breakdown": [...],
   "top_topics": [{"tag": t, "wrong": n}]}` (top 3). `_compute_failure_patterns`
   takes an optional `now` (default `datetime.utcnow()`) so tests can
   pin the window; the demo seed data is generated relative to
   `date.today()`, so the default now keeps the demo recent window
   meaningful. No change to training, split, or model.
2. **Zero-submissions empty state (honesty gap).** Today the card
   shows "No wrong submissions yet" whenever `total_wrong == 0` —
   including when `total_submissions == 0` (nothing synced at all),
   which reads as "you never fail" when the truth is "no data".
   Split the states: `total_submissions == 0` shows a distinct
   "No submissions synced yet — sync your Codeforces account" state;
   `total_wrong == 0` (with submissions) keeps the existing state.
3. **UI: recent block.** Small "Last 30 days" section in the same
   card: wrong count in the window + verdict chips + top recent
   topic, or "no wrong submissions in the last 30 days". Shown only
   when `total_submissions > 0`. EN + BN copy; hedged wording only.

## Out of scope

- No LLM anywhere (pure aggregation, as approved).
- No sync on live (needs Khalid's live login + handle connect).
- No dashboard copy of the card (Analytics is its home).
- No change to signal thresholds, stage buckets, or the shipped
  model/split.

## Verification

- New tests in `tests/test_failure_patterns.py`: recency window
  (explicit `now`, rows inside/outside the window), zero-rows
  payload (total 0, `recent.total_wrong` 0, `enough_data` false),
  endpoint shape includes `recent`.
- Full pytest green except the 2 pre-existing UTC flakes.
- `npm run build` (tsc + vite) passes.
- Dev backend restarted; real endpoint (Khalid dev data) + demo
  endpoint return the `recent` block; zero-case proven via a
  throwaway dev user with a handle row but no submissions (deleted
  afterwards, dev DB left with only Khalid).
- Live after deploy: health 200, /docs 404, demo endpoint 200 with
  `recent`, real endpoint 401 without auth.
