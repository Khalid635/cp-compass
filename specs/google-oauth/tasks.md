# Google OAuth sign-in — tasks

- [ ] 1. Backend module `backend/app/google_oauth.py` (auth URL, signed
  state, token exchange, userinfo) + config vars + `.env.example`
- [ ] 2. Model: `User.google_id` (unique) + nullable `password_hash`;
  migration `0005_google_oauth.py` (batch_alter_table)
- [ ] 3. Endpoints in `main.py`: `GET /api/v1/auth/google`,
  `POST /api/v1/auth/google/callback` (link/create, TOTP-aware)
- [ ] 4. Tests `backend/tests/test_google_oauth.py` (10 cases, mocked
  Google) — all pass; full pytest suite green except the 2 known
  UTC flakes if run 00:00–06:00 Dhaka
- [ ] 5. Migration check on a scratch SQLite DB (`alembic upgrade head`)
- [ ] 6. Frontend: client.ts methods, useAuth methods, Google button on
  AuthPage (login + register), `GoogleCallbackPage` + `/auth/callback`
  route, i18n keys (en + bn)
- [ ] 7. Frontend build passes (tsc + vite); before/after screenshots
  (desktop + true-390 mobile, dev :5173) viewed
- [ ] 8. Commit (one commit, only batch files) + push via askpass
- [ ] 9. Render deploy: `GET /api/v1/auth/google` 404 → 503; live
  health 200, /docs 404; Google button renders on live login page
  (desktop + mobile shots) — copy all shots to
  `~/workspace/shots-google-oauth/`
- [ ] 10. Report: commit hash, what works, browser task needed (Cloud
  Console client + Render env vars), E2E pending Khalid's click
