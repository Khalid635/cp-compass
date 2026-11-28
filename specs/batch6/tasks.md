# Batch 6 — tasks

- [x] Spec written (specs/batch6/spec.md)
- [x] Arena probe: 10 agents on the cookie+CSRF design; winner +
      scores in specs/batch6/arena-result.md (NO full-100 winner)
- [x] N1: register rate limit (shared resend bucket) + keep old code
      until new one is sent; tests
- [x] N2: PasswordResetToken model + migration 0009; forgot/reset
      endpoints + mailer + frontend pages (EN+BN); tests
- [x] N3: _client_ip last-XFF-entry in prod, peer in dev; tests
- [x] N4 backend: HttpOnly cookies + CSRF (probe winner's design);
      get_current_user via cookie; refresh/logout cookie-based; SSE
      cookie auth; AuthOut without tokens; tests
- [x] N4 frontend: client.ts credentials + CSRF header; useAuth
      rework; legacy localStorage keys removed at boot; layout.tsx
      EventSource withCredentials; types.ts; build green
- [x] #8: audit.py + call sites (login, lockout, refresh reuse,
      rate-limit 429s, totp); caplog tests
- [x] #3: Neon cpcompass_app role + grants; MIGRATION_DATABASE_URL;
      dev-against-Neon verification; Render env switch (manual);
      live health + login after (role + dev-Neon verification done; Render DATABASE_URL switch is Khalid's manual step, AFTER this deploy; migration 0009 already on live Neon as owner)
- [x] #22: npm uninstall @react-three/drei; build green
- [x] Batch 5 endpoints rate-limited (stream, public-profile, ics,
      /u/{handle}); tests
- [x] Showcase PNGs renamed to *-v2 + references updated; build serves
      new files
- [x] Sync wart: last_synced_at set on done even with 0 new; test
- [x] Full pytest (114 + new, 0 failed) + frontend build (139 passed, 0 failed; build green)
- [ ] Commit (batch6 files only) + push; live DB-backed probes; probe
      deleted; live users back to 1
- [ ] Final report: commit hash, files, test counts, live evidence,
      arena result, honest limits
