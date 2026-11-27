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

### Methodology (numbers from the live model artifact, retrained 2026-11-27)

- **Data:** n=208 rows — 197 synthetic demo rows (seed.py, rng-generated with
  known per-tag solve rates) + 11 real rows from the owner's account. The
  model mostly reflects the demo persona until real submissions accumulate;
  the UI labels it "Trained on demo data" until then. Retraining is manual
  (Settings → Retrain model).
- **Split:** stratified RANDOM 80/20 (train 166 / test 42, random_state=42).
  **Not split by user or by time — said plainly:** rows from the same user
  appear on both sides of the split, so the test AUC is optimistic for a
  brand-new user. A time-based split is planned with the Batch 3 backtest.
- **Held-out test (n=42):** Random Forest **AUC 0.856, Brier 0.129,
  accuracy 0.881**; 5-fold CV AUC 0.818, CV Brier 0.148. Logistic Regression
  (test AUC 0.815) and gradient boosting (test AUC 0.827, but CV AUC 0.988 —
  overfit ~200 rows, predicted degenerate 0.00/0.99) were evaluated and
  rejected. The deep Random Forest (CV AUC 0.960) and HistGB (CV AUC 0.977)
  were rejected for the same overfitting reason.
- **Baseline:** the rule-based recommendation score (0.35W+0.30D+0.20R+0.15P)
  used as a probability — test **AUC 0.34, Brier 0.389, accuracy 0.262**.
  It scores BELOW chance as a solvability probability, because it deliberately
  rewards weak tags and harder problems: it is a practice-priority score, not
  a solvability score. The ML model had to beat it on both held-out AUC and
  Brier to ship — and it did, by a wide margin.
- **Calibration:** sigmoid calibration was tried (CalibratedClassifierCV,
  cv=3). On this training run CV Brier was 0.147 calibrated vs 0.148
  uncalibrated, so this artifact shipped WITH sigmoid calibration. (An
  earlier 197-row run rejected calibration, 0.157 vs 0.143 — the shipped
  choice is re-decided on every retrain and recorded in the artifact.)
- **Log-loss: NOT computed.** The evaluation records accuracy, Brier score
  and AUC only. Log-loss (and a calibration curve) will be added with the
  Batch 3 backtest — no log-loss number is claimed anywhere until then.
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
