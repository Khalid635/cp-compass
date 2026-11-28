# Batch 8 — ML training split: random → by-time (re-evaluated, evidence-gated)

## Goal
Decide, with fresh evidence, whether the shipped ML training evaluation
should switch from the random stratified 80/20 split to a leakage-free
by-time split (Batch 3 follow-up decision). Do NOT assume the switch is a
win — the Batch 3 numbers already warn against it (see below).

## Background (measured, Batch 3, 2026-11-27)
- Random split (n=204: 193 demo + 11 real; test n=41): RF AUC 0.773 /
  Brier 0.164 / log-loss 0.490; logreg 0.712; Elo 0.664; rule 0.320.
- By-time split (cutoff 2026-10-01, demo-only; train 157 / test 36):
  RF AUC 0.683 / Brier 0.209 / log-loss 0.607; logreg 0.776; Elo 0.706;
  rule 0.203.
- Two red flags in the Batch 3 numbers:
  (1) the model ranking FLIPS between splits — RF wins random, logreg
  wins by-time (and Elo 0.706 beats RF 0.683 forward);
  (2) the by-time test set is n=36 — an AUC gap of ~0.09 is inside the
  noise of a 36-row test set (SE ~0.08), so neither gap is conclusive.
- The demo seed is UNCHANGED since Batch 3 (only helper functions added
  in Batch 4/5) — the Batch 3 numbers should reproduce; re-measure to
  confirm.
- What the split actually controls: the final model is refit on ALL rows
  either way. The split only controls the evaluation numbers stored in
  the artifact, the ship-rule gate, and the calibration decision.
  Switching the split does not change predictions unless it changes the
  ship/model decision.

## Pre-registered decision criteria (written BEFORE the new measurements)
SWITCH iff ALL of:
(a) By-time RF beats the rule baseline on held-out AUC and Brier at the
    2026-10-01 cutoff AND at >= 3 of 5 tested cutoffs (2026-09-01,
    2026-09-15, 2026-10-01, 2026-10-15, 2026-11-01).
(b) By-time RF is within 0.05 test AUC of logreg at the primary cutoff
    and at the majority of cutoffs — else the evidence says the MODEL
    (not just the split) needs reselection, which is a separate
    follow-up, not a silent keep-RF.
(c) The by-time test set is usable at the shipped relative cutoff:
    n_test >= 20 and both classes present; otherwise fall back to
    random with the reason recorded in the artifact.
(d) The switch does not silently unship a working model: if by-time RF
    fails the ship gate while random passes, DO NOT switch; report that
    the forward evidence does not support the current model and
    recommend more real data / model reselection as follow-up.
If any criterion fails: NO switch. Report the numbers honestly, keep
the random-split training, and record the by-time metrics in the
artifact/README as the honest forward estimate (already the README's
lead number per Batch 3).

## Measurements (new, this batch)
1. Re-run `backend/scripts/backtest.py` fresh (protocols A+B+C) on
   current data; confirm reproduction of the Batch 3 numbers.
2. `backend/scripts/split_sensitivity.py` (new, committed): random split
   across seeds [42, 1, 7, 123, 2026]; by-time across the 5 cutoffs
   above (demo-only, protocol B method); by-time on the COMBINED
   dataset (demo + real rows) at the primary cutoff — the shipped
   path's actual evaluation.
3. Results written to `specs/batch8/sensitivity-results.json`
   (committed) and summarized in the Decision section below.

## Implementation (NO SWITCH path — what is actually built)
- `ml.py`: add leakage-free time-aware row building for the combined
  dataset (per-user pre-cutoff tag stats, train labels "solved before
  cutoff", test labels "eventually solved"; mirrors
  `backtest.time_aware_rows`, generalized to multiple users).
  Cutoff rule: RELATIVE — the first-attempt timestamp at the 80th
  percentile of rows (newest ~20% as test), recomputed each retrain;
  a fixed date would rot. Fall back to the random stratified split
  when the by-time test set is too small (< 20 rows) or single-class;
  the artifact records which split ran and why.
- Artifact evaluation: primary metrics are the by-time ones; the
  random-split RF numbers are also recorded (`evaluation_random_split`)
  for traceability. `/ml/status` serves the primary evaluation — its
  shape is unchanged (`baseline` / `logreg` / `random_forest` /
  `hist_gb` / `calibration` under `evaluation`).
- Ship rule unchanged in form (RF beats baseline on held-out AUC +
  Brier), applied to the by-time holdout. Calibration check unchanged
  (CV Brier on the by-time train rows).
- README Methodology: rewrite the split paragraph + numbers from the
  fresh measurements (both splits shown, by-time led).
- `backtest.py`: unchanged (it already implements both protocols;
  protocol A stays the random reference).

## Tests (new, `backend/tests/test_batch8.py`)
- Relative-cutoff builder: train/test row counts sane at the
  80th-percentile cutoff; test rows all first-attempted on/after the
  cutoff; train rows all before.
- Leakage: a problem whose only OK is after the cutoff has train
  label 0 and its tag acceptance excludes post-cutoff solves; test
  rows have prev_attempts 0 when first-attempted after the cutoff.
- Fallback: with a cutoff that leaves < 20 test rows (or a
  single-class test set), training falls back to random and records
  the split kind in the artifact.
- Ship-gate behavior on by-time metrics (unit-level, synthetic rows).
- Full pytest passes (2 pre-existing UTC flakes may fail 00:00-06:00
  Dhaka).

## Non-goals
- No model re-tuning, no new features, no candidate changes
  (logreg-vs-RF reselection is a follow-up if the evidence demands
  it — not smuggled in here).
- No frontend changes, no new endpoints, no migration (no schema
  change).
- No change to protocol C / precision@k (still unmeasurable at n=4
  in pool).

## Verification
- Fresh backtest + sensitivity results committed; Decision section
  below filled with numbers.
- Full pytest (expect 140+; currently 140).
- Retrain on dev (demo + dev DB) -> artifact shows the new split;
  `GET /api/v1/ml/status` shows it.
- Commit ONLY Batch 8 files; push; live-verify (health 200,
  /docs 404, DB-backed register/login probes, probes deleted, users
  back to 1, live alembic 0010).

## Decision (measured 2026-11-28; see specs/batch8/sensitivity-results.json)
- Fresh backtest reproduction: EXACT. Protocol A RF 0.773 / 0.164 /
  0.490, logreg 0.712; protocol B (2026-10-01, 157/36) RF 0.683 /
  0.209 / 0.607, logreg 0.776; protocol C still unmeasurable (4/36
  in pool). The demo seed is unchanged since Batch 3.
- Random-split seed sensitivity (combined n=204, test n=41): RF test
  AUC 0.773-0.870 across seeds [42, 1, 7, 123, 2026], mean 0.826.
  The shipped seed 42 (0.773) is the LOWEST — the random-split number
  is not seed-lucky. But the RF-vs-logreg ranking on random splits is
  mixed (RF wins 3/5 seeds, logreg 2/5; means 0.826 vs 0.802).
- By-time cutoff sensitivity (demo-only): RF test AUC 0.683-0.761
  (mean 0.714) across cutoffs 09-01 / 09-15 / 10-01 / 10-15 / 11-01;
  logreg 0.771-0.812 (mean 0.787). Logreg beats RF forward at ALL 5
  cutoffs (gaps 0.089, 0.097, 0.093, 0.051, 0.031). On Brier and
  log-loss the forward picture is mixed (logreg better on log-loss at
  4/5, Brier 3/5) — AUC is the consistent logreg edge.
- Combined-dataset by-time at 2026-10-01: train 166 / test 38
  (36 demo + 2 real), RF 0.694 / 0.202 / 0.590, logreg 0.787,
  Elo 0.683, rule 0.197. Relative 80th-percentile cutoff
  (2026-09-27): train 163 / test 41 (39 demo + 2 real), RF 0.740,
  logreg 0.779. Real rows are 2 of 38-41 test rows — the forward
  evaluation is still ~95% synthetic demo data.
- Criteria: (a) PASS — RF beats the rule baseline on AUC+Brier at the
  primary cutoff and at 5/5 cutoffs. (b) FAIL — RF is within 0.05 test
  AUC of logreg at only 1/5 cutoffs (11-01, n=14); logreg wins forward
  5/5. (c) PASS — relative-cutoff test set n=41, both classes present.
  (d) PASS — by-time RF passes the ship gate at all cutoffs, so a
  switch would not unship the model (moot: (b) fails).
- DECISION: NO SWITCH. The by-time evaluation itself is sound and RF
  passes its gate forward — but the forward evidence consistently
  favors logistic regression over the shipped Random Forest. Switching
  the split while keeping RF would certify the second-best model as
  "the forward-validated model". The split question cannot be answered
  without the model question. Follow-up (separate batch, not this
  one): model reselection — logreg as the forward candidate —
  re-measured when real rows grow past a handful. Until then the
  random-split evaluation stays the ship gate, and the by-time
  evaluation is recorded in the artifact + README as the honest
  forward estimate (it now ships in the artifact, see below).

## What this batch ships instead (NO SWITCH path)
- `ml.py`: the by-time evaluation moves INTO the training path as an
  informational block — `evaluation["by_time"]`, computed at every
  retrain from the combined dataset with a relative 80th-percentile
  cutoff and leakage-free rows. It NEVER gates shipping and NEVER
  changes the fitted model; if it cannot run (too few post-cutoff
  rows, single-class test set, any error) it records
  `{"ran": false, "reason": ...}` and training continues. The random
  split stays the ship gate, the calibration check, and the evaluation
  served as primary. `/ml/status` serves the `by_time` block too.
- `backtest.time_aware_rows` moves into `ml.py` (single
  implementation; backtest keeps an alias so its tests are untouched).
- README Methodology: fresh numbers (seed range, cutoff table,
  logreg-forward finding, combined by-time, real-row share) + this
  decision, stated plainly.
- `ml.py` docstring NOTE: Batch 8 addendum with the decision.
