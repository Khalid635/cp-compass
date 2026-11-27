# AI Hint Ladder — tasks

- [x] Spec (this folder) — decisions: 3 steps, order-enforced, 10/day, DB cache, Gemini Flash REST, no solution/code
- [x] Backend: `app/hints.py` — Gemini REST client + prompt builder + usage counting
- [x] Backend: `app/config.py` — GEMINI_API_KEY / GEMINI_MODEL / HINT_DAILY_LIMIT / HINT_HTTP_TIMEOUT_S (lazy)
- [x] Backend: `app/models.py` — `AiHint` table (unique user/problem/step/lang)
- [x] Backend: migration `0006_ai_hints.py` (upgrade + downgrade, SQLite-safe)
- [x] Backend: `app/main.py` — GET + POST `/problems/{contest_id}/{index}/hints` (+ HintIn model)
- [x] Backend: `.env.example` — GEMINI_* names only
- [x] Tests: `tests/test_hints.py` — 503 / happy path / order / cache / limit / 502 / prompt guardrail / auth
- [x] Frontend: `api/types.ts` + `api/client.ts` — HintStep/HintsResponse, getHints/requestHint
- [x] Frontend: i18n dict.ts + en.ts + bn.ts — hint keys
- [x] Frontend: ProblemDetail.tsx — AI hints card (steps, usage, demo/solved states)
- [x] Verify: pytest full suite (2 pre-existing UTC flakes only) + frontend build
- [x] Verify: dev backend restart + local hint endpoint proof (real vs mocked — state which)
- [x] Commit (one) + push via askpass; Render redeploy; live verify health 200, /docs 404, hint endpoint behaviour
- [x] Report: commit hash, rate limit chosen, what remains unverified
