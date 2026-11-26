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

- Frontend: https://cp-compass.vercel.app *(deploy in progress — see below)*
- Backend: https://cp-compass-api.onrender.com *(deploy in progress)*

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

- Held-out test (n=40): **AUC 0.834** vs the rule-based baseline AUC 0.317.
  Logistic Regression and gradient boosting were evaluated and rejected
  (linear extrapolation failed; boosting overfit ~200 rows and predicted
  degenerate 0.00/0.99). Calibration did not help and was not shipped.
- **A prediction, not a guarantee.** The model only learned from problems
  already attempted — problems never tried are not in its training data, so
  treat the % as a hint. The model is labelled "Trained on demo data" until
  your own submission history is large enough; retrain from Settings.
- Selection bias: the training set is attempted problems only, so it is
  biased toward problems you chose to try.

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
