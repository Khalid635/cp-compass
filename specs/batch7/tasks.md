# Batch 7 — tasks

- [x] Spec written (specs/batch7/spec.md)
- [x] Migration 0010: RLS on + per-table policies (Postgres-only, SQLite no-op); downgrade drops policies + disables RLS
- [x] db.py: set_rls_user / clear_rls_user + after_transaction_end re-apply hook (Postgres-only, SQLite no-op)
- [x] auth.py: get_current_user sets variable; _new_refresh_token sets it; refresh_tokens restructured (SELECT -> set -> atomic UPDATE); revoke_refresh_token / revoke_all_refresh_tokens set it
- [x] main.py: pre-auth endpoints set variable after resolving the user (register, verify-email, resend-code, forgot/reset-password, google callback, totp verify, public profile); _issue_email_code / _issue_reset_token set it; sync_stream session sets it
- [x] sync.py: _run_job_sync sets variable to the job's user; claim/recover unchanged (sync_jobs exception)
- [x] ml.py: _db_sets sets the variable per user + restores the caller's context
- [x] Tests: test_rls.py (SQLite roundtrip always runs; Postgres isolation probes gated on env URLs)
- [x] Full pytest on laptop venv (139 + new, 0 failed) — 140 passed, 6 skipped, 2026-11-28
- [x] Dev verification on throwaway Neon DB cpcompass_rls_dev (direct-SQL probes as cpcompass_app + API probes with two users + full endpoint smoke); DB dropped afterwards — DONE 2026-11-28: 7/7 RLS tests on real Postgres; API isolation all PASS (export, revisions, review 404, public-profile 404->200, dashboards, wrong-password 401); sync worker proved via /sync/status failed + CF error; 27-endpoint smoke, no 500s; DB dropped + verified gone
- [x] Commit (batch7 files only) + push; Render deploy; live alembic 0010 verified; live DB-backed probes (register/login, cross-user isolation); probes deleted, live users back to 1 — DONE 2026-11-28: commit 75ed806, deploy dep-dc5b5iu0tbcc73e1ljb0 live; startup migration did NOT apply 0010 (likely MIGRATION_DATABASE_URL unset on Render → falls back to app-role DATABASE_URL) — applied manually as owner; live probes all PASS; users back to 1. OPEN: set MIGRATION_DATABASE_URL on Render to the owner URL (Khalid's manual step) or future migrations will silently fail at startup.
