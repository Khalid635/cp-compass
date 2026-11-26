# CP Compass

তোমার Codeforces ডাটা দেখে বলে দেয় — আজ কোন প্রবলেম করবে, কোন টপিকে তুমি দুর্বল, আর কোন প্রবলেমটা আবার দেখার সময় হয়েছে।

## Stack (সব ফ্রি)

- **Frontend:** Vite + React 19 + TypeScript + Tailwind CSS 4, Recharts, TanStack Query
- **Backend:** FastAPI + SQLAlchemy + SQLite (dev) / Neon Postgres (prod)
- **Deploy (পরে):** Vercel (frontend) + Render free (backend) + Neon free (Postgres) — মোট খরচ ৳০

## Status

MVP (P1) শেষ + ল্যাপটপে যাচাই করা 2026-11-26: Dashboard, Practice, Revision, Landing, Demo, Login/Register + Codeforces sync + demo mode (seed data)। Build পাস, `/api/health` OK, Khalid_Bin_Masud handle-এ live sync যাচাই করা। P2 (Analytics, Problem detail, Contests, Settings) পরে।

পূর্ণ পরিকল্পনা: `~/workspace/goals/become-a-skilled-software-developer-and-ai-ml-engineer/files/cp-compass-full-plan/cp-compass-full-plan.pdf`

## Run (dev, laptop Windows)

```bash
# Frontend — D:\Projects\cp-compass\frontend
npm install
npm run dev        # http://localhost:5173

# Backend — D:\Projects\cp-compass\backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8004
```

- Demo (লগইন ছাড়া, seed ডাটা): http://localhost:5173/demo
- আসল ব্যবহার: Register → Codeforces handle যুক্ত করো → "Sync now"
- আসল SECRET_KEY-এর জন্য `backend\.env.example` কপি করে `.env` বানাও — `.env` কখনো commit করবে না (dev default শুধু local test-এর জন্য)।

## Structure

```
frontend/   # Vite + React app
backend/    # FastAPI app (auth, CF sync, recommendations, revisions)
```
