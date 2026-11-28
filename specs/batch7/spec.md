# Batch 7 — Row-Level Security (RLS) on all 21 Neon tables

Status: spec first, then build.
Base: dfa885e (Reticle removal landed). Laptop only, via SSH.
Commit ONLY batch7 files. Backend security is automatic (standing rule).
Approved by Khalid 2026-11-28 13:23 ("হ্যাঁ, RLS on + policy লেখো").

Live state (verified 2026-11-28): 22 tables in public schema (21 app
tables + alembic_version), ALL with RLS off. Live alembic 0009, 1 user.
Live app runs as cpcompass_app since the DATABASE_URL switch
(2026-11-28 16:02). The app role (Batch 6) has CRUD on all 21 tables,
SELECT on alembic_version, USAGE on schema, default privileges for
future tables/sequences, CREATE/TRUNCATE false.

## 0. Design — how RLS knows who "you" are

The app connects as ONE shared role (cpcompass_app), so Postgres
cannot tell users apart by itself. The mechanism:

- **Session variable** `app.current_user_id`, set per request with
  `SELECT set_config('app.current_user_id', '<id>', true)` — the
  third argument makes it transaction-local (`SET LOCAL` semantics):
  it dies with the transaction, so it can NEVER leak across pooled
  connections to another request.
- **Policies** compare the row's owner to that variable:
  `user_id = nullif(current_setting('app.current_user_id', true), '')::int`.
  `nullif` turns '' into NULL so an empty value can never cast-error;
  an unset/empty variable makes the comparison NULL (false) — rows
  are invisible, never visible by default.
- **The commit trap:** `SET LOCAL` dies at every `db.commit()`, and
  this codebase commits mid-request all over (token issuance,
  set_goal then settings_data, sync checkpoints, _issue_email_code).
  So `set_rls_user()` stores the id in `session.info["rls_user_id"]`
  and a `Session` `after_transaction_end` hook (non-nested only)
  re-applies it after every commit AND rollback. Verified by a
  Postgres test (set → commit → query still scoped) and by the full
  endpoint smoke. On SQLite the helper and the hook are no-ops, so
  the 139-test SQLite suite is unaffected.

### Policy shapes (one line per table)

Strict = `FOR ALL ... USING (user_id = <cur>) WITH CHECK (user_id = <cur>)`
where `<cur>` is the nullif expression above. Pre-auth tables get a
SELECT exception `(<cur> IS NULL OR ...)` — see §0.1.

| table | policy |
|---|---|
| users | SELECT: `id = <cur> OR <cur> IS NULL` (pre-auth login/OAuth reads by email); INSERT: permissive (registration creates the row pre-auth); UPDATE/DELETE: strict on `id = <cur>` |
| cf_accounts | SELECT: `user_id = <cur> OR <cur> IS NULL` (public profile looks up by handle with no auth); INSERT/UPDATE/DELETE: strict |
| problems | SELECT: permissive (global catalog, one row per problem, shared); INSERT/UPDATE/DELETE: require a user context (`<cur> IS NOT NULL`) — sync and set_preference always run with one |
| submissions | strict |
| ai_hints | strict |
| hint_usage | strict |
| postmortem_analysis | strict |
| postmortem_usage | strict |
| rating_history | strict |
| revisions | strict |
| sync_jobs | SELECT/UPDATE: `user_id = <cur> OR <cur> IS NULL` (worker claim + stale-job recovery run with no user context — §0.2); INSERT/DELETE: strict |
| problem_notes | strict |
| problem_preferences | strict |
| daily_stats | strict |
| weekly_reports | strict |
| refresh_tokens | SELECT: `user_id = <cur> OR <cur> IS NULL` (refresh/logout look up by token hash pre-auth); INSERT/UPDATE/DELETE: strict |
| email_verifications | strict on all ops (endpoints resolve the user by email first, then set the variable — §2) |
| password_reset_tokens | SELECT: `user_id = <cur> OR <cur> IS NULL` (reset looks up by token hash pre-auth); INSERT/UPDATE/DELETE: strict |
| totp_secrets | strict |
| backup_codes | strict |
| handle_verifications | strict |
| alembic_version | RLS on + SELECT-only policy `USING (true)` for the app role (no INSERT/UPDATE/DELETE policies → denied for the app role; migrations run as owner, which bypasses RLS) |

No FORCE RLS anywhere: the table owner (Neon owner role, used only
by migrations and by us via psql) must keep bypassing RLS, or
migrations and owner maintenance would break. Documented here, not
silent.

### 0.1 Why the IS NULL exceptions exist (and what they cost)

Four tables genuinely need pre-auth reads, because the credential
IS the lookup key and no user is known yet:

- `users` SELECT: login/register/verify/resend/forgot and the
  Google callback read by email/google_id before any session exists.
- `password_reset_tokens` SELECT: reset-password looks up by token
  hash. The token is a random 32-byte value (SHA-256 stored) —
  not brute-forceable.
- `refresh_tokens` SELECT: refresh/logout look up by token hash.
  Same 32-byte random token argument.
- `cf_accounts` SELECT: the public profile looks up by handle with
  no auth. Handles are public on Codeforces anyway.
- `sync_jobs` SELECT/UPDATE: the worker (§0.2).

Cost, stated honestly: a direct connection as cpcompass_app with no
variable set can read THOSE tables (and only those). The 16 strict
tables stay invisible. The pre-auth endpoints are all parameterized
(audited — no SQL injection path), and the app role's credential
alone is already game-over territory today (no RLS at all). The win
is real: every authenticated request is now scoped, so a forgotten
`user_id` filter (the classic IDOR) returns nothing instead of
someone else's rows, and a stolen app-role credential cannot dump
submissions, notes, hints, TOTP secrets, or backup codes.

The alternative considered and rejected: SECURITY DEFINER lookup
functions for the token tables. More Postgres machinery, harder to
test on SQLite, and the same residual exposure would remain for the
users-table login read anyway. The exception is the smaller change.

### 0.2 The sync worker

The worker loop claims jobs with NO user context
(`_claim_next_job`: oldest pending job, any user) and recovers stale
jobs the same way (`recover_stale_jobs`: all running jobs with an
expired lease). Both run in sessions that never set the variable —
that is why sync_jobs SELECT/UPDATE carry the IS NULL exception.
`_run_job_sync` DOES know the user (job.user_id is passed in), so
it sets the variable right after loading the user + job, and every
query inside `run_sync` (including the per-page checkpoint commits)
is scoped by the hook.

Known behaviour note: `recover_stale_jobs` is also called from
`enqueue_sync`, which runs inside an AUTHENTICATED request (variable
= the requester). There it now recovers only the requester's stale
jobs, not everyone's. A stale job of another user is recovered at
startup (lifespan, no variable) or when that user next enqueues.
Acceptable: the lease + startup recovery is the real safety net, and
the worker being alive is what claims pending jobs anyway.

### 0.3 ML training reads all users — preserved, scoped per user

`ml._db_sets` iterates ALL users and reads each one's submissions /
rating history / handle (the model trains on demo + every user's
data, as before). With RLS it now sets the variable to each user in
turn before reading that user's rows, and RESTORES the caller's
context afterwards (save/restore in a finally). Behaviour is
identical to pre-RLS; each read is properly scoped to one user at a
time. The per-user `sources` in the model metadata are unchanged
(they are already scoped to the requesting handle in ml_status).

### 0.4 What RLS does NOT do

- It does not replace the app's own `user_id` filters — those stay
  (defence in depth, and the SQLite dev/test path has no RLS).
- It does not protect the `users`/`problems` SELECT paths (see the
  table above) — those are open by documented design.
- It does not stop a compromised app ROLE from writing junk rows to
  the strict tables IF it also sets the variable — RLS scopes reads
  and writes to the claimed user, it does not authenticate the claim.
  The JWT is still the authentication.

## 1. Migration 0010 — enable RLS + policies, one atomic step

- New migration `0010_rls.py`, revises 0009. All DDL in ONE
  transaction (Alembic online mode already wraps it): if any
  statement fails, nothing is half-enabled. RLS with no policies
  would break the app — policies are created in the SAME migration
  as the `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`, never alone.
- Postgres-only: `upgrade()` and `downgrade()` return immediately
  when `op.get_bind().dialect.name != "postgresql"`, so the SQLite
  roundtrip test and the whole SQLite suite keep passing unchanged.
- Downgrade drops every policy and disables RLS on all 22 tables.
- Policies are `TO cpcompass_app` (the role exists — Batch 6).
  The migration runs as owner (MIGRATION_DATABASE_URL), which is
  also why the owner bypass matters (§0).

## 2. App changes (all Postgres-gated, SQLite no-ops)

### 2.1 `backend/app/db.py` — the mechanism

- `set_rls_user(db, user_id)`: stores `user_id` in
  `session.info["rls_user_id"]` and executes
  `SELECT set_config('app.current_user_id', '<id>', true)` when the
  session's dialect is postgresql. No-op on SQLite.
- `clear_rls_user(db)`: removes the stored id and sets the variable
  to '' (same dialect guard).
- `Session` `after_transaction_end` listener (non-nested only):
  re-applies the stored id after every commit/rollback. Uses
  `session.get_bind()` (works on 1.4 and 2.0).

### 2.2 `backend/app/auth.py` — set the context where the user is known

- `get_current_user`: after loading the user, `set_rls_user(db,
  user.id)` — the choke point for every authenticated endpoint.
- `_new_refresh_token(db, user_id)`: `set_rls_user(db, user_id)`
  first (covers login/verify/2fa/google/refresh, all of which call
  `issue_tokens` after a commit may have cleared the variable).
- `refresh_tokens(db, raw)`: RESTRUCTURED — SELECT the token row by
  hash first (SELECT exception allows it), `set_rls_user(db,
  row.user_id)`, THEN the atomic `UPDATE ... WHERE revoked_at IS
  NULL` (same race semantics: the second concurrent refresh still
  updates 0 rows and hits the reuse path). Reuse detection and
  `revoke_all_refresh_tokens` unchanged in behaviour.
- `revoke_refresh_token(db, raw)`: after finding the row by hash,
  `set_rls_user(db, row.user_id)` before mutating it (logout is
  pre-auth).
- `revoke_all_refresh_tokens(db, user_id)`: `set_rls_user(db,
  user_id)` first (reset-password calls it pre-auth).

### 2.3 `backend/app/main.py` — pre-auth endpoints set the context after resolving the user

Rule: resolve via the public credential (email / token / hash),
then `set_rls_user` BEFORE any further DB read/write on that user's
rows. Sites:

- `register`: after the new user is created + committed,
  `set_rls_user(db, user.id)` before `_issue_email_code`.
  (Re-register of an unverified email: same, with `existing`.)
- `verify_email`: after loading the user by email,
  `set_rls_user(db, user.id)` before the EmailVerification query.
- `resend_code`: same — set after loading the user, before
  `_issue_email_code`.
- `forgot_password`: set after loading the user, before
  `_issue_reset_token`.
- `reset_password`: after the token row resolves to a user,
  `set_rls_user(db, row.user_id)` before mutating the token/user.
  (`revoke_all_refresh_tokens` also sets it — §2.2.)
- `google_callback`: after the user is resolved/created (either
  branch), `set_rls_user(db, user.id)` before the google_id link
  assignment + commit. (Without this, the link UPDATE is blocked:
  strict users UPDATE with no variable.)
- `totp_verify`: after loading the user from the pre_token,
  `set_rls_user(db, user.id)` before the BackupCode/TotpSecret
  reads. (The pre_token proves the password step.)
- `public_profile` (GET /u/{handle}, no auth): after the account
  resolves AND `public_profile` is confirmed, `set_rls_user(db,
  user.id)` before `services.public_profile_stats`. The handle
  lookup itself uses the cf_accounts SELECT exception.
- `_issue_email_code(db, user)`: `set_rls_user(db, user.id)` first
  (covers the post-send old-row delete, which runs after a commit).
- `_issue_reset_token(db, user)`: `set_rls_user(db, user.id)` first
  AND again right before the post-send old-token delete (a commit
  sits between; the hook re-applies anyway — the explicit call is
  belt-and-braces and self-documenting).
- `sync_stream` `_generate`: after creating each poll session,
  `set_rls_user(db, user_id)` (user_id is known from the outer
  scope). Without this the stream always reports
  `{"status": "never"}`.

### 2.4 `backend/app/sync.py` — worker session

- `_run_job_sync(job_id, user_id)`: after loading user + job,
  `set_rls_user(session, user_id)` before `run_sync`. (The loads
  themselves use the users/sync_jobs SELECT exceptions.)
- `_claim_next_job` / `recover_stale_jobs` / `worker_loop`: NO
  change — they run with no variable and rely on the sync_jobs
  SELECT/UPDATE exception (§0.2).

### 2.5 `backend/app/ml.py` — per-user scoping in the training loop

- `_db_sets`: save the caller's context (`db.info.get(...)`),
  `set_rls_user(db, user.id)` before reading each user's rows,
  restore the caller's context in a `finally`. (Without the
  restore, a retrain would leave the session scoped to the last
  user in the loop and the endpoint's later `user.last_retrain_at`
  write would be blocked for any other requester.)

### 2.6 Known dead check (documented, not silently fixed)

- `handle_start`'s `taken` pre-check (`CfAccount` with
  `user_id != requester`) can never see another user's account
  under RLS — it always returns None. The `handle_norm` UNIQUE
  constraint in `_link_handle` is the real cross-user guard (same
  400, via IntegrityError). Leave the check in place (it still
  works on SQLite) with a comment saying so.

## 3. Tests

- Full existing suite on the laptop venv (SQLite) must pass
  unchanged: target 139 passed + new tests, 0 failed. The 2 UTC
  flakes only fail 00:00–06:00 Dhaka — do not chase them.
- New `backend/tests/test_rls.py`:
  - `test_migration_0010_roundtrip` (SQLite, always runs): alembic
    upgrade 0009 → 0010 → downgrade → upgrade on a tmp SQLite DB
    does not crash and changes nothing (migration is a Postgres
    no-op there). Mirrors `test_migration_0008_roundtrip`.
  - Postgres-gated tests (skip unless `TEST_POSTGRES_OWNER_URL`
    and `TEST_POSTGRES_APP_URL` are set in the environment — never
    in code): run alembic to head on a throwaway DB as owner, then
    as the app role prove: (a) with variable=A, SELECT submissions
    shows only A's rows; UPDATE/DELETE of B's row affects 0 rows;
    INSERT for A works, INSERT for B raises a policy violation;
    (b) with no variable, strict tables return 0 rows while users /
    problems / token tables remain readable (the documented
    exceptions); (c) set → commit → query still scoped (the hook);
    (d) the public-profile path (variable set to the target user
    after the opt-in check) sees that user's aggregates.
- No test ever contains a credential: URLs come from the
  environment only.

## 4. Dev verification (throwaway Neon DB — NEVER live)

1. As owner (psql, URL read transiently from
   `backend/.env.production`, never printed): `CREATE DATABASE
   cpcompass_rls_dev`. Run alembic upgrade head against it
   (MIGRATION_DATABASE_URL pointed at the new DB). Grant the app
   role on the new DB exactly as Batch 6 did for neondb
   (CONNECT + USAGE schema + CRUD tables + USAGE/SELECT sequences
   + default privileges).
2. Run `test_rls.py` Postgres-gated against it.
3. Run the dev backend against it as the app role (uvicorn,
   DATABASE_URL = app-role URL for the new DB, throwaway
   SECRET_KEY generated for the run only): register two probe
   users via the dev outbox (codes from backend/dev_outbox.log),
   log in as A, and prove through the API: A's dashboard/export
   show only A's data; `POST /revisions/review` with B's revision
   id → 404; `GET /u/{B-handle}` → 404 while B is private, 200
   with aggregates after B opts in; public profile never leaks
   email/user id. Full endpoint smoke (health, login, sync status,
   dashboard, recommendations, hints GET, postmortems list, demo
   reads — no 500s from RLS).
4. `DROP DATABASE cpcompass_rls_dev` + delete the probe rows'
   parent DB. Verify it is gone.

### 4.1 Results (2026-11-28, all on the laptop)

- Alembic upgrade head on the throwaway DB: 0009 → 0010 clean.
  After the run: 22 tables, alembic 0010, RLS on 22/22, 40
  policies (list verified against §0).
- `test_rls.py` Postgres-gated: **7/7 passed** (strict
  isolation, no-context exceptions, context survives commit,
  public-profile path, problems writes need context,
  alembic_version read-only, SQLite roundtrip). One real Postgres
  rule found by the run and fixed in the migration: an INSERT
  policy may carry ONLY a WITH CHECK clause — Postgres rejects a
  USING clause on INSERT ("only WITH CHECK expression allowed for
  INSERT"); the migration's `_policy()` helper now omits USING for
  INSERT. One test-only fix: raw-SQL INSERTs into submissions must
  supply `created_at` (Python-side default only).
- Full suite (SQLite): **140 passed, 6 skipped, 0 failed**.
- API probes (dev backend :8005 as the app role, two users
  a7@rls.dev / b7@rls.dev via the dev outbox): export A = [9001,
  9002] only, export B = [9003] only; A revisions list empty;
  A review of B's revision → 404; /u/BeeRLS → 404 while private,
  200 with aggregates after B opted in, no email leak;
  dashboards A solved=1/recent_total=2, B solved=1/recent_total=1;
  wrong-password login → 401. Sync worker proved: POST /sync as A
  → 202, job reached `failed` with "handle: User with handle
  AppleRLS not found" (fake handle — the worker claimed the job,
  set the context, ran, and wrote the failure back under RLS).
- Endpoint smoke: 27 endpoints, **no 500s**. Two 422s are
  validation, not server errors: /calendar + /demo/calendar called
  without their required date param; hints POST without the
  required `step` field. (Probing notes: every mutation needs the
  CSRF token first — GET /auth/csrf mints it; `.test` email domains
  are rejected by email-validator — `.dev` works; register has a
  ~60 s resend cooldown; /auth/me returns no user id — ids were
  read as owner via psql.)
- Cleanup: dev server stopped (port 8005 free), DB dropped,
  verified gone (no `cpcompass%` database remains).

## 5. Live apply — order matters

1. Push the code FIRST (deploy). The new code sets the variable;
   with RLS still off that is a harmless no-op, so the app works
   through the whole deploy.
2. The deploy's startup migration (owner, MIGRATION_DATABASE_URL)
   applies 0010 automatically. After the deploy goes live, check
   the live alembic version: if it is 0010, done. If it is still
   0009, apply manually as owner from the laptop (`alembic upgrade
   head` with the owner URL) and re-check.
3. NEVER apply 0010 before the code deploys: the old code sets no
   variable, so strict tables would go invisible the moment RLS
   turns on.
4. Live verify (§6). The deploy window itself can briefly serve
   degraded reads from the OLD container while the new one starts
   (RLS applies at startup, traffic switches after) — seconds, one
   user, noted here and in the report.

## 6. Live verification (after deploy)

- Health 200, /docs 404.
- Live alembic 0010 (psql as owner, read-only).
- DB-backed register/login probes via the live API (dev outbox
  does not exist in prod — the Resend test-domain limit means a
  verification mail to a non-owner address fails; use the
  Batch 6 pattern: insert the probe user directly as owner with
  an Argon2 hash via the app's own `hash_password`, email
  verified, then log in through the API).
- Cross-user isolation probe on live: probe user A (logged in)  attempts `POST /revisions/review` with a revision id owned by
  Khalid's account → 404, and A's dashboard/export show only A's
  (empty) data.
- Probe users deleted; live users back to 1; live alembic 0010.
- RLS spot-check as owner: all 22 tables relrowsecurity = true,
  policies present per §0.

### 6.1 Results (2026-11-28)

- Commit **75ed806** (9 files, +1158/−5), pushed; remote HEAD =
  local HEAD. Render deploy **dep-dc5b5iu0tbcc73e1ljb0** live
  16:55 Dhaka.
- **The deploy's startup migration did NOT apply 0010**: live
  alembic stayed 0009, RLS 0/22, policies 0 after the deploy went
  live (health 200). Most likely cause: Render has no
  MIGRATION_DATABASE_URL set, so it falls back to DATABASE_URL —
  which is now the app-role URL — and the app role cannot ALTER
  tables it does not own, so the migration failed at startup and
  the app's try/except swallowed it (health stayed 200). The
  Render log was not checked (connector is read-only, no logs).
- **Applied manually as owner from the laptop** (`alembic upgrade
  head`, owner URL): 0009 → 0010 clean; live alembic 0010, RLS
  22/22, 40 policies, live users still 1. No restart needed — the
  running code already sets the variable.
- Live probes (probe users inserted as owner with Argon2 hashes
  via the app's own `hash_password`, email verified; ids 17, 18):
  login A + B OK through the live API; A export empty, B export
  [9103] only; A review of B's revision → 404; /u/LiveB → 404
  while private, 200 after opt-in, no email leak; wrong-password
  login → 401; /sync/status 200. **All PASS, no fails.**
- Cleanup: probe users + probe problem deleted; live users back
  to 1, live submissions back to 0, 0 probe rows left.
- **Open follow-up (needs Khalid's manual step): set
  MIGRATION_DATABASE_URL on Render to the owner URL**, or every
  future migration will silently fail at startup the same way
  (the app keeps serving, alembic stays behind). Do NOT set it
  without his go-ahead — it is the owner credential.

## 7. Commit + push

- Commit ONLY batch7 files (specs/batch7/, migration 0010,
  backend/app/{db,auth,main,sync,ml}.py, tests/test_rls.py).
  Normalize line endings to match each blob. Push via the
  Python-stdin winreg GITHUB_TOKEN + throwaway askpass pattern
  (deleted right after); token never printed.

## Honest limits (to state in the final report)

- RLS is defence in depth, not authentication: it scopes what the
  shared app role can see per request; the JWT is still the auth.
- The five documented exceptions (§0.1–0.2) mean a no-context
  app-role connection can still read users / token hashes /
  handles / sync jobs / the problem catalog. The 16 strict tables
  cannot be read that way.
- The deploy window (§5.4) can briefly serve degraded reads.
- Live verification of a second real user's full flow is bounded
  by the Resend test domain (same as Batch 6); the isolation
  proof on live uses a DB-inserted probe user, as before.
