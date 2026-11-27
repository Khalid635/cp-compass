# Batch 3 tasks

- [x] Spec (this file's parent spec.md) — scope, protocols, non-goals
- [x] `backend/app/ml.py`: add `log_loss` to `_metrics()`; update docstring snapshot line
- [x] `backend/scripts/backtest.py`: protocols A (random split + log-loss + Elo baseline + calibration table), B (by-time split 2026-10-01, 157/36), C (precision@k vs rule score / ML / Elo / random)
- [x] Run the backtest; record the real numbers in `backend/scripts/backtest-results.json`
- [x] `backend/tests/test_backtest.py`: log-loss sanity, cutoff counts, scorer agreement with `services.recommend()`
- [x] Retrain (demo + dev DB) so the artifact carries log-loss; restart dev backend; verify `GET /api/v1/ml/status`
- [x] README Methodology rewrite with the fresh numbers + honest limits
- [x] pytest full suite; commit + push (batch files only)
