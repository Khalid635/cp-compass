# Security fixes (reel checklist gaps) - spec

## Problem
The reel-checklist security check of 2026-11-27 (19 points, report in the
agent workspace: cp-compass-reel-security-check-2026-11-27.md) found 16/19
PASS and 3 GAPs, plus one stale-config nit. Khalid approved fixing all 3
gaps on 2026-11-27 20:20. H1 (HttpOnly cookies) stays DEFERRED - not in
this batch. The Resend test-domain mail problem is a separate decision -
not in this batch.

## Verified facts (checked 2026-11-27, before building)
- #13 python-jose==3.5.0 has GHSA-3qf3-8w2g-rqmx / PYSEC-2026-4298
  (algorithm-confusion guard bypassed by DER-encoded public keys).
  Exploitability here is limited (app verifies HS256 symmetric tokens
  only, never asymmetric keys), but the library is unmaintained (last
  release 2022) with no fixed release - migrate, do not bump.
- PyJWT 2.15.1 (latest on PyPI, checked 2026-11-27) has 0 known vulns on
  OSV. PyJWT 2.10.1 is NOT clean (GHSA-2gx3-rcp4-g85q, PyJWKClient JWKS
  amplification, fixed in 2.14.0) - pin 2.15.1, not 2.10.1.
- Only backend/app/auth.py imports jose (`from jose import JWTError, jwt`,
  line 19). totp.py uses pyotp, not jose. No test file references jose or
  jwt directly - tests go through the API + auth.issue_tokens, so the
  swap is transparent to them.
- #12: GET /api/docs, /redoc, /openapi.json return 200 on live; no debug
  flags exist anywhere (Dockerfile CMD is plain uvicorn, no --debug).
- #16: db.py sets no connect_args for Postgres - SSL depends entirely on
  the URL carrying ?sslmode=require. Laptop .env.production URL does
  carry it (boolean check only); Render value assumed same, not verified.
- render.yaml pins CORS_ORIGINS https://cp-compass.vercel.app, but the
  live frontend is cp-compass-phi.vercel.app (live dashboard value is
  correct; the blueprint value is a stale hazard only).

## Fixes (4)
1. PyJWT migration: auth.py `from jose import JWTError, jwt` -> `import
   jwt`; catch `jwt.InvalidTokenError` instead of `JWTError` (2 sites:
   decode_totp_pending_token, get_current_user). requirements.txt:
   `python-jose[cryptography]==3.5.0` -> `PyJWT==2.15.1`. Encode/decode
   call signatures are identical (HS256, algorithms=[...]). Refresh
   rotation and TOTP flows are untouched. Update SECURITY.md
   Dependencies section to record the migration.
2. Docs off in production: FastAPI(docs_url=None, redoc_url=None,
   openapi_url=None) when ENV == "production"; dev keeps docs.
3. DB SSL in code: db.py connect_args {"sslmode": "require"} for
   non-SQLite URLs; SQLite keeps check_same_thread=False. Do not touch
   Render env vars or read secrets.
4. render.yaml CORS_ORIGINS -> https://cp-compass-phi.vercel.app.

## Out of scope
- Resend custom-domain / test-domain mail restriction and the silent
  mail-failure surfacing in register-retry/resend-code paths.
- H1 HttpOnly cookies. Dashboard-apply batch. Font changes.

## Verification
- pytest stays green (was 39/39) + 1 new test: JWT round-trip works,
  wrong-key / tampered / expired tokens -> 401.
- Frontend build passes (tsc + vite).
- Local boot check: ENV=production + strong SECRET_KEY -> /docs, /redoc,
  /openapi.json return 404, /api/v1/health returns 200; ENV=development
  -> /docs returns 200.
- Live verify with DB-backed probes, not health only: after deploy,
  /docs and /openapi.json return 404 on live; register with a throwaway
  +probe alias -> 503 expected (Resend test-domain limit - the row is
  still created, see main.py register), login correct password -> 403
  "Email not verified", login wrong password -> 401. Delete the probe
  account + code row from live Neon afterwards; login afterwards -> 401.
