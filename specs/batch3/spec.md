# Batch 3 — Recommender backtest + README results

## Goal
Measure, honestly, how good the CP Compass recommender and solvability model
actually are — and close the ML methodology gaps the premium batch marked
(log-loss never computed, random split leaks, no rating-gap baseline, no
calibration curve, no recommender precision@k).

## Data (what exists, stated plainly)
- Demo seed (`backend/app/seed.py`): 355 submissions, 193 unique problems,
  first attempts 2026-06-02 to 2026-11-28, 212 solved. SYNTHETIC —
  rng-generated with known per-tag solve rates. The backtest measures the
  pipeline on the demo persona, not real-user generalization.
- Real rows (dev DB, user Khalid_Bin_Masud): 16 submissions, 11 unique rated
  problems. Too few for any split — reported as a count only, never split.
- Live artifact (2026-11-27 retrain): n=208 (197 demo + 11 real), test AUC
  0.856, Brier 0.129, baseline AUC 0.34. The artifact is stale vs the current
  seed (seed changed since training), so this batch retrains.

## Protocols (all in `backend/scripts/backtest.py`)
- **A. Random-split protocol (the shipped one) + log-loss.** Same 80/20
  stratified split (random_state=42) as `app.ml.train_model`, same candidates
  (logreg, constrained RF, HistGB). Adds log-loss for every model and the
  baselines, plus a calibration table (predicted-probability bins vs actual
  solve rate) for the shipped RF. Closes the "log-loss: NOT computed" gap on
  the protocol the artifact actually uses.
- **B. By-time split (leakage-free, forward in time).** Cutoff 2026-10-01:
  train = problems first attempted before the cutoff (157), test = problems
  first attempted on/after it (36). Features for every row are computed from
  submissions BEFORE the cutoff only (tag stats, rating at first attempt,
  prev_attempts); training labels are "solved before the cutoff", test labels
  are "eventually solved" (the future outcome being predicted). Same models
  and baselines as A, same metrics. This is the number the README must lead
  with for generalization — the random-split AUC is optimistic.
- **C. Recommender precision@k (forward).** At the cutoff, rank the live CF
  problemset (fetched once, cached locally) with (1) the rule-based score
  0.35W+0.30D+0.20R+0.15P, (2) the ML-predicted P(solve), (3) the Elo
  baseline, (4) random. Take top-3 / top-5 / top-10 of each; report how many
  were attempted after the cutoff and, of those, how many were solved
  (precision@k = solved / attempted, with the attempted count shown).
  The "attempted" filter is selection-biased (the user chose what to try) —
  say so; report counts, not just rates.
- **Elo baseline (rating-gap only).** P = 1 / (1 + 10^((problem_rating -
  user_rating) / 400)). Reported on both splits alongside the rule-based
  score baseline, as review #3 asked.

## Code changes
- `backend/app/ml.py`: `_metrics()` gains `log_loss` (additive only — no
  change to training, split, model selection or the ship rule). The module
  docstring's stale "LIVE numbers" snapshot line is updated to the retrain.
- `backend/scripts/backtest.py` (new): implements A, B, C; prints a
  human-readable report and writes `backend/scripts/backtest-results.json`
  (committed — the README numbers are traceable to it). The CF problemset
  cache (`problemset-cache.json`) is gitignored.
- `backend/tests/test_backtest.py` (new): log-loss in `_metrics` is sane;
  time-aware row builder gives 157/36 at the 2026-10-01 cutoff and test rows
  have prev_attempts 0; the script's rule-score reimplementation agrees with
  `services.recommend()` on the real DB user for a sample of problems.
- `README.md`: the Methodology section is rewritten with the fresh numbers
  from the retrain + backtest (both protocols, Elo baseline, log-loss,
  calibration table, precision@k, honest limits).

## Non-goals
- No change to the shipped training split, model selection or ship rule —
  the by-time protocol is an evaluation this batch; switching the shipped
  training to it is a follow-up decision, not smuggled in here.
- No frontend changes, no new endpoints, no model re-tuning.

## Verification
- `python scripts/backtest.py` runs end-to-end and prints the JSON report.
- `pytest` passes (2 pre-existing UTC-vs-local flakes may fail 00:00-06:00
  Dhaka — test_10_heatmap_full_history, test_11_cumulative_solved).
- Retrain refreshes `backend/ml_model.joblib` with log-loss in the
  evaluation; dev backend restarted; `GET /api/v1/ml/status` shows it.
- Commit + push (one commit, batch files only; Reticle changes untouched).

## Honest limits (go in the README, not just here)
- Demo data is synthetic; the backtest validates the pipeline, not
  real-user generalization. Real rows = 11.
- By-time test set is small (n=36 problems); precision@k denominators are
  small. Report counts everywhere.
- The CF problemset is fetched live; if Codeforces is unreachable the
  precision@k part reports "not run" instead of inventing a pool.
