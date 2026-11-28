# Tasks — Batch 4: Contest post-mortem (full report + AI analysis)

- [x] Verify data honesty: CF API user.status (latest 2026-10-26) + dev DB (16 subs) — Khalid did NOT play Round 1138; spec records it
- [x] Backend computation: services._compute_postmortem + postmortem + postmortem_list (+ cf.contest_list cached 1h)
- [x] AI module: app/postmortem_ai.py (generate + cache + daily limit 5) + models PostmortemAnalysis/PostmortemUsage + migration 0007 + config POSTMORTEM_DAILY_LIMIT
- [x] Endpoints: GET /postmortems, /postmortems/latest, /postmortems/{id}, GET/POST /postmortems/{id}/analysis + demo endpoints (no demo AI)
- [x] Tests: tests/test_postmortem.py (21 new) — full pytest 94 passed, 0 failed
- [x] Frontend: types + client + Postmortems.tsx + Postmortem.tsx + routes (app + demo) + nav item + i18n EN/BN
- [x] Frontend build passes (npm run build)
- [x] Dev verify: backend restarted (PID 27640, migration 0006 -> 0007), real endpoints on Khalid dev data (231: 2 subs 1 solved; 4: 4 subs 1 solved; 2292 has_data false), demo endpoints, real Gemini proof (contest 231, 26.5s, cached repeat free)
- [ ] Commit ONLY batch files + push (askpass pattern, token never printed)
- [ ] Live verify: Render deploy id, health 200, /docs 404, demo 200, real 401 no-auth, DB-backed probe (throwaway +alias, deleted, live users back to 1)
- [ ] Final report: commit hash, files, exact test counts, live evidence, honest limits
