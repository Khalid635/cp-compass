# CP Compass

তোমার Codeforces ডাটা দেখে বলে দেয় — আজ কোন প্রবলেম করবে, কোন টপিকে তুমি দুর্বল, আর কোন প্রবলেমটা আবার দেখার সময় হয়েছে।

## Stack (সব ফ্রি)

- **Frontend:** Vite + React 19 + TypeScript + Tailwind CSS 4, Recharts, TanStack Query
- **Backend:** FastAPI + SQLAlchemy + SQLite (dev) / Neon Postgres (prod)
- **Deploy (পরে):** Vercel (frontend) + Render free (backend) + Neon free (Postgres) — মোট খরচ ৳০

## Status

MVP build চলছে — P1: Dashboard, Practice, Revision, Landing, Demo, Login/Register + Codeforces sync + demo mode (seed data)। P2 (Analytics, Problem detail, Contests, Settings) পরে।

পূর্ণ পরিকল্পনা: `~/workspace/goals/become-a-skilled-software-developer-and-ai-ml-engineer/files/cp-compass-full-plan/cp-compass-full-plan.pdf`

## Run (dev)

```bash
# Frontend
npm install
npm run dev        # http://localhost:5173

# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate   # laptop (Windows)
pip install -r requirements.txt
uvicorn main:app --port 8004
```

## Structure

```
frontend/   # Vite + React app
backend/    # FastAPI app (auth, CF sync, recommendations, revisions)
```
