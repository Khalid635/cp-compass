# Security fixes - tasks

- [x] Spec + tasks written (specs/security-fixes/)
- [x] Fix 1: auth.py jose -> PyJWT; requirements.txt pin PyJWT==2.15.1;
      SECURITY.md Dependencies updated
- [x] Fix 2: docs disabled when ENV == "production" (main.py)
- [x] Fix 3: db.py connect_args sslmode=require for non-SQLite
- [x] Fix 4: render.yaml CORS_ORIGINS -> https://cp-compass-phi.vercel.app
- [x] New test: JWT round-trip + wrong-key/tampered/expired -> 401
- [x] pytest green (39 + new); frontend build passes
- [x] Local boot: prod ENV -> /docs,/redoc,/openapi.json 404 + health 200;
      dev ENV -> /docs 200
- [ ] Commit + push to main (askpass pattern, .bat deleted after)
- [ ] Live verify: /docs,/openapi.json 404; probe register/login
      (403/401); probe account + code row deleted; login after -> 401
- [x] Report: commit hash, per-fix live evidence, anything unverified
- [x] Fix 2b: production detection uses ENV OR non-SQLite DATABASE_URL
- [x] render.yaml declares ENV=production
- [x] Re-verify: pytest green; wiring check (3 env combos)
- [x] Commit + push (fresh deploy) + live verify
- [x] Root cause: cryptography missing (transitive via python-jose);
      added cryptography==50.0.2 pin
- [x] Fresh-venv verify: pip install + import + pytest 40 passed

## Live verification record (2026-11-27, deploy dep-dc4pn2q9lscs73elb110 LIVE)
- /docs, /redoc, /openapi.json -> 404 on live; /api/v1/health -> 200;
  /api/v1/auth/me without token -> 401.
- Probe khalidmasud22+secfix20261127b@gmail.com: register -> 503
  (expected: Resend test-domain limit; user row still created), login
  correct password -> 403 "Email not verified", login wrong password
  -> 401. Probe account + 1 code row deleted from live Neon; login
  afterwards -> 401. Remaining live users: 1 (Khalid's own verified
  account, untouched).
- NOT verified live: PyJWT token issuance on live (no verified probe
  account can exist - the verification email cannot arrive for a
  +alias address; Khalid's own account must not be used for probes).
  PyJWT round-trip is proven by pytest 40/40 incl. the fresh-venv run
  and the local boot check.
- Egress proxy flakiness during the probe: several RemoteDisconnected /
  IncompleteRead errors on the VM side; all retried to a clean result.
