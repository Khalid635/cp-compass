# Tasks — Batch 2: Failure-pattern analysis

## Backend

- [x] 1. `Submission.passed_test_count` (Integer, nullable) in `models.py`
- [x] 2. Alembic migration `0004_passed_test_count.py` (add column)
- [x] 3. `sync.py`: store `passedTestCount` on new submissions
- [x] 4. `sync.py`: `backfill_passed_test_counts` (max 5 pages/run), called at end of `run_sync` only when NULL rows exist
- [x] 5. `services.py`: `_compute_failure_patterns(rows)` + `failure_patterns(db, user_id)` (verdict breakdown, test stages, per-topic signals, per-problem top 8, wrong-before-first-AC, coverage)
- [x] 6. `services.py`: `problem_detail` submissions include `passed_test_count`
- [x] 7. `main.py`: `GET /api/v1/analytics/failures` + `GET /api/v1/demo/analytics/failures`
- [x] 8. `seed.py`: deterministic `passed_test_count` on demo submissions + `failure_patterns_payload()` via the shared computation
- [x] 9. `tests/test_failure_patterns.py`: breakdown, bucketing + NULLs, signal thresholds, thin flags, backfill, problem_detail count

## Frontend

- [x] 10. `types.ts`: `FailurePatternsData` (+ `passed_test_count` on problem-detail submissions)
- [x] 11. `client.ts`: `failurePatterns()` + `demoFailurePatterns()`
- [x] 12. `Analytics.tsx`: "Failure patterns" card (breakdown, stages, per-topic, per-problem, empty/low-data states)
- [x] 13. `ProblemDetail.tsx`: "Tests" column + one-line summary when wrong >= 2 with test data
- [x] 14. i18n: all new strings in `dict.ts` + `en.ts` + `bn.ts`

## Verify

- [x] 15. Backend: `pytest` green (incl. new tests)
- [x] 16. Frontend: `npm run build` passes
- [x] 17. Live smoke: real `/analytics/failures` (16 subs), demo endpoint, demo Analytics render
- [x] 18. Screenshots: desktop + mobile (Analytics failures card, Problem Detail tests column)
- [x] 19. Commit on laptop (Batch 2 only; landing tweaks are a separate commit after)
