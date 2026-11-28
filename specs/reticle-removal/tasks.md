# Reticle removal — tasks

- [x] Remove reticle import + plugin entry from frontend/vite.config.ts
- [x] Verify file matches HEAD (git diff empty) and package.json untouched
- [x] Frontend build green (npm run build)
- [x] Restart dev server (PID 24188) cleanly; localhost:5173 responds
- [x] CDP screenshot of localhost:5173 viewed — gold frame gone on all 4 edges
- [ ] Commit specs/reticle-removal/ only; push
- [ ] Live health 200 on /api/v1/health
