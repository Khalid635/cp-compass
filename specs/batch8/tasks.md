# Batch 8 — tasks

- [x] Recon: repo state (HEAD ea16f57, Batch 7 done), ml.py training path, backtest.py protocols, Batch 3 numbers
- [x] Spec written with pre-registered decision criteria (spec.md)
- [x] Re-run backend/scripts/backtest.py fresh; Batch 3 numbers reproduced EXACTLY (RF random 0.773, by-time 0.683)
- [x] Wrote backend/scripts/split_sensitivity.py (random seeds + by-time cutoffs + combined by-time)
- [x] Ran sensitivity; wrote specs/batch8/sensitivity-results.json
- [x] Filled Decision section in spec.md: NO SWITCH — criterion (b) fails (logreg beats RF forward 5/5 cutoffs)
- [x] Implement by-time evaluation block in ml.py (relative 80th-percentile cutoff, leakage-free rows, informational only, never gates shipping, never fails training)
- [x] Move backtest.time_aware_rows into ml.py (single implementation; backtest keeps alias)
- [x] Serve by_time block in model_status (/ml/status)
- [x] Update README Methodology with fresh numbers + decision
- [x] Update ml.py docstring NOTE with Batch 8 addendum
- [x] New tests backend/tests/test_batch8.py (builder, leakage, fallback, ship-gate)
- [x] Full pytest passes (140+; 2 UTC flakes only 00:00-06:00 Dhaka) — 148 passed, 6 skipped
- [x] Retrain on dev; GET /api/v1/ml/status shows the new state
- [x] Commit ONLY Batch 8 files; push
- [x] Live-verify: health 200, /docs 404, DB-backed register/login probes, probes deleted, users back to 1, live alembic 0010
- [x] Report back to parent: decision + numbers, tests, commit, deploy id, live verification
