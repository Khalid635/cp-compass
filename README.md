# CP Compass

A Codeforces progress tracker that turns your submissions into a daily plan:
which topic is weak, which problem to solve today, and what to revise.

- **Dashboard** — rating, solved, streak, revision due, rating history, topic
  strength, daily activity heatmap, recent submissions
- **Practice** — recommendations with a score and a reason, filter pills,
  saved views, Save for Later / Not Interested, ML solvability %
- **Revision** — spaced repetition (1 / 3 / 7 / 14 / 30 days) with
  Again / Hard / Good / Easy grading
- **Analytics** — peak rating, difficulty distribution, success rate by
  difficulty, milestones, contest auto-analysis, how predictions work
- **Calendar** — practice calendar from daily stats
- **Weekly report** — weekly summary with vs-last-week deltas + JSON export
- **Problem detail** — submissions, revision status, Markdown notes
- **Settings** — handle, weekly goal, data export, account deletion

English + Bangla UI. Dark theme with a single teal accent.

## Live demo

- Frontend: https://cp-compass-phi.vercel.app
- Backend: https://cp-compass-api-1j9a.onrender.com (Render free tier — sleeps after ~15 min idle; first load takes up to a minute)

The demo account (`/demo`) is seeded example data and is strictly read-only.

## Stack

- Frontend: React 19 + Vite + TypeScript + Tailwind CSS 4, shadcn/ui,
  Recharts, Three.js (landing hero only)
- Backend: FastAPI + SQLAlchemy + Alembic, Argon2 password hashing,
  JWT access (15 min) + refresh tokens (7 days, revocable)
- ML: scikit-learn Random Forest solvability model (see below)
- Database: Postgres (Neon free tier in production, SQLite locally)
- Hosting (all free tier): Vercel (frontend) + Render (backend) + Neon (DB)

## Run locally

```bash
# backend
cd backend
py -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env                          # fill in SECRET_KEY
uvicorn app.main:app --host 127.0.0.1 --port 8004

# frontend
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```

Migrations run automatically at backend startup. The ML model trains in a
background thread on first boot if no artifact exists yet.

## How predictions work

The solvability model predicts the chance you solve a recommended problem.
It is a **constrained Random Forest** (300 trees, max depth 4, min 10 samples
per leaf), trained on your attempted problems: user rating, problem rating,
rating difference, per-tag acceptance, previous attempts, and tag one-hots.
One training row per (user, problem); the label is 1 if the user eventually
solved it, 0 otherwise.

### Methodology (numbers from the live model artifact, retrained 2026-11-27 20:15 UTC)

- **Data:** n=204 rows — 193 synthetic demo rows (seed.py, rng-generated with
  known per-tag solve rates) + 11 real rows from the owner's account. The
  model mostly reflects the demo persona until real submissions accumulate;
  the UI labels it "Trained on demo data" until then. Retraining is manual
  (Settings → Retrain model).
- **Split:** stratified RANDOM 80/20 (train 163 / test 41, random_state=42).
  **Not split by user or by time — said plainly:** rows from the same user
  appear on both sides of the split, so the test AUC is optimistic for a
  brand-new user. The Batch 3 backtest ran a leakage-free by-time split
  (below) — use its numbers for generalization, not the random-split ones.
- **Held-out test, random split (n=41):** Random Forest **AUC 0.773, Brier
  0.164, log-loss 0.490, accuracy 0.756**; 5-fold CV AUC 0.816, CV Brier
  0.157, CV log-loss 0.475. Logistic Regression: test AUC 0.712, log-loss
  0.580. Gradient boosting (HistGB): test AUC 0.912, Brier 0.025, log-loss
  0.273 — but 92.7% of its test predictions are extreme (<0.05 or >0.95)
  and its CV AUC is 0.981, the overfitting signature; on the by-time split
  it collapses (below), so it stays rejected. The deep Random Forest
  (CV AUC 0.960) was rejected for the same overfitting reason.
- **Baselines, same test set (n=41):** the rule-based recommendation score
  (0.35W+0.30D+0.20R+0.15P) used as a probability → **AUC 0.320, Brier
  0.378, log-loss 0.976**. It scores BELOW chance as a solvability
  probability, because it deliberately rewards weak tags and harder
  problems: it is a practice-priority score, not a solvability score. The
  rating-gap-only Elo baseline (P = 1 / (1 + 10^((problem − user) / 400)))
  is much stronger → **AUC 0.664, Brier 0.212, log-loss 0.597**. The shipped
  Random Forest beats both on held-out AUC, Brier and log-loss.
- **By-time split (Batch 3 backtest, cutoff 2026-10-01, demo persona only):
  train 157 / test 36.** Features and training labels use only submissions
  before the cutoff; test labels are "eventually solved". Random Forest:
  **test AUC 0.683, Brier 0.209, log-loss 0.607**. Logistic Regression:
  AUC 0.776, Brier 0.202, log-loss 0.585 — better than the forest on this
  small forward set (n=36, too small to conclude it is better; not a
  reason to switch the shipped model). Elo: AUC 0.706, Brier 0.275,
  log-loss 0.847. Rule score: AUC 0.203, Brier 0.388, log-loss 0.999.
  HistGB collapses forward: AUC 0.522, log-loss 1.427, 80.6% of its
  predictions extreme — confident and wrong. **Headline: the random-split
  AUC (0.773) is optimistic; the forward AUC (0.683) is the honest
  generalization number.**
- **Calibration:** sigmoid calibration was tried (CalibratedClassifierCV,
  cv=3). On this training run CV Brier was 0.157 calibrated vs 0.157
  uncalibrated (a tie), so this artifact shipped WITHOUT calibration.
  (The previous run shipped with it, 0.147 vs 0.148 — the choice is
  re-decided on every retrain and recorded in the artifact.) Random-split
  test calibration, shipped forest (n=41): predicted 0.2–0.4 → actual 0.00
  (n=3); 0.4–0.6 → 0.67 (n=12); 0.6–0.8 → 0.80 (n=15); 0.8–1.0 → 0.91
  (n=11); the forest never predicts below 0.2 or above 0.95 on this set.
  By-time test calibration (n=36): 0.2–0.4 → 0.14 (n=7); 0.4–0.6 → 0.80
  (n=10); 0.6–0.8 → 0.63 (n=19) — roughly the right direction, noisy at
  this size.
- **Log-loss: computed since Batch 3** (it was never computed before).
  Random-split test: forest 0.490, logreg 0.580, HistGB 0.273, Elo 0.597,
  rule score 0.976. By-time test: forest 0.607, logreg 0.585, Elo 0.847,
  rule score 0.999, HistGB 1.427.
- **Recommender precision@k: NOT measurable yet.** At the 2026-10-01
  cutoff the demo persona ranked the live Codeforces problemset (995
  problems in the [rating, rating+200] band, never attempted before the
  cutoff) by rule score, ML probability, Elo and random. The top-3/5/10/
  50/100 of EVERY ranking contained zero of the 36 problems the user
  actually attempted after the cutoff — only 4 of those 36 were even in
  the candidate pool (the other 32 were outside the rating band). The
  usable comparison is the predictor AUC on those 36 problems (above),
  not a precision@k. The minimum-score threshold (25) filtered nothing:
  all 995 in-band problems passed it.
- **A prediction, not a guarantee.** The model only learned from problems
  already attempted — problems never tried are not in its training data, so
  treat the % as a hint. The model is labelled "Trained on demo data" until
  your own submission history is large enough; retrain from Settings.
- **Selection bias:** the training set is attempted problems only, so it is
  biased toward problems you chose to try.

The full evaluation (all candidates, CV + test, calibration) is stored in
the model artifact (`backend/ml_model.joblib`, gitignored) and served by
`GET /api/v1/ml/status` — the numbers above are a snapshot of it, not a
second source of truth. If a retrain changes them, update this section.
The backtest that produced the by-time and precision@k numbers is
`backend/scripts/backtest.py`; its full output is committed at
`backend/scripts/backtest-results.json` (rerun: `python scripts/backtest.py`).

## Deploy (free tier)

- `render.yaml` — Render Blueprint: one free Docker web service (Singapore).
  Set `DATABASE_URL` (Neon) and `SECRET_KEY` in the Render dashboard.
- `frontend/vercel.json` — Vite project, SPA fallback. Set `VITE_API_BASE`
  to the Render backend URL in the Vercel project settings.
- `.github/workflows/ci.yml` — pytest + frontend build on every push/PR.
- See `docs/architecture.md` for the system diagram and the free-tier
  limits (Neon 100 CU-hours/mo, Render 750 hrs/mo + 15-min sleep,
  Vercel Hobby 100 GB/mo, personal non-commercial use).

## License

MIT — see `LICENSE`.
