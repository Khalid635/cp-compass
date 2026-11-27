# Tasks — Mistake-pattern mining

- [x] Verify Batch 2 baseline (tests, dev real+demo endpoints, live demo+401, Neon audit)
- [x] Backend: `recent` block in `_compute_failure_patterns` (30d window, `now` param)
- [x] Tests: recency window, zero-rows payload, endpoint shape
- [x] Frontend: zero-submissions empty state + recent block (Analytics card)
- [x] i18n: new keys EN + BN (`dict.ts` types + `en.ts` + `bn.ts`)
- [x] pytest full suite green (minus 2 pre-existing UTC flakes)
- [x] Frontend build passes
- [x] Dev backend restart + endpoint proof (real, demo, zero-case throwaway user, cleaned up)
- [x] Screenshots viewed: demo Analytics EN desktop + EN mobile (true 390) + BN desktop, 0 console errors
- [ ] Commit + push (own files only; Reticle untouched)
- [ ] Live verify after deploy (health 200, /docs 404, demo 200 with `recent`, real 401)
