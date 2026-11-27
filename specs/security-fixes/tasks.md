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
- [ ] Report: commit hash, per-fix live evidence, anything unverified
