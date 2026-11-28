"""Row-Level Security on all 21 app tables + alembic_version (batch 7).

Design (specs/batch7/spec.md §0): the app connects as ONE shared role
(cpcompass_app), so each session carries the authenticated user's id in
the transaction-local setting app.current_user_id, and the policies
below compare the row's owner to it.

  CUR = nullif(current_setting('app.current_user_id', true), '')::int
  -- NULL when the variable is unset or empty: an unset context can
  never match a row, and can never raise a cast error.

Policy shapes:
- strict (16 tables): FOR ALL, user_id = CUR. Every read/write in an
  authenticated request is scoped; a forgotten user_id filter returns
  nothing instead of someone else's rows.
- users / cf_accounts / password_reset_tokens / refresh_tokens: SELECT
  also allows CUR IS NULL, because those tables are genuinely read
  pre-auth (login by email, token lookup by hash, public profile by
  handle). INSERT/UPDATE/DELETE stay strict.
- sync_jobs: SELECT/UPDATE also allow CUR IS NULL, because the worker
  claims jobs and recovers stale jobs with no user context.
- problems: SELECT permissive (global shared catalog); writes require
  a user context (CUR IS NOT NULL).
- alembic_version: RLS on + SELECT-only permissive policy (migrations
  run as owner, which bypasses RLS).

No FORCE RLS: the table owner must keep bypassing RLS, or migrations
and owner maintenance would break.

Postgres-only: on SQLite (dev/test) upgrade() and downgrade() are
no-ops, so the SQLite suite and the migration roundtrip test are
unaffected. Runs as owner (MIGRATION_DATABASE_URL). All DDL is one
transaction (Alembic online mode): RLS and its policies are created
together, never alone.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-28
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

APP_ROLE = "cpcompass_app"

# NULL when the session variable is unset or empty.
CUR = "nullif(current_setting('app.current_user_id', true), '')::int"

# user_id-owned tables with strict scoping on every operation.
STRICT_TABLES = (
    "submissions",
    "ai_hints",
    "hint_usage",
    "postmortem_analysis",
    "postmortem_usage",
    "rating_history",
    "revisions",
    "problem_notes",
    "problem_preferences",
    "daily_stats",
    "weekly_reports",
    "totp_secrets",
    "backup_codes",
    "handle_verifications",
    "email_verifications",
    "sync_jobs",  # INSERT/DELETE strict; SELECT/UPDATE get the worker
    # exception below (sync_jobs is listed here only for the
    # INSERT/DELETE policies -- see _sync_jobs_policies).
)

# Tables whose SELECT must also work with no user context (pre-auth
# reads): the credential IS the lookup key and no user is known yet.
# INSERT/UPDATE/DELETE stay strict.
PREAUTH_SELECT_TABLES = (
    "users",  # read by email / google_id at login, register, OAuth
    "cf_accounts",  # public profile looks up by handle, no auth
    "password_reset_tokens",  # reset looks up by token hash
    "refresh_tokens",  # refresh / logout look up by token hash
)

ALL_TABLES = (
    "users",
    "cf_accounts",
    "problems",
    "submissions",
    "ai_hints",
    "hint_usage",
    "postmortem_analysis",
    "postmortem_usage",
    "rating_history",
    "revisions",
    "sync_jobs",
    "problem_notes",
    "problem_preferences",
    "daily_stats",
    "weekly_reports",
    "refresh_tokens",
    "email_verifications",
    "password_reset_tokens",
    "totp_secrets",
    "backup_codes",
    "handle_verifications",
    "alembic_version",
)


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _enable(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def _policy(name: str, table: str, command: str, using: str | None,
            check: str | None = None) -> None:
    # Postgres forbids a USING clause on INSERT policies: only WITH
    # CHECK is allowed there.
    if command == "INSERT":
        assert check is not None
        sql = (f'CREATE POLICY "{name}" ON "{table}" FOR INSERT '
               f'TO {APP_ROLE} WITH CHECK ({check})')
    else:
        sql = (f'CREATE POLICY "{name}" ON "{table}" FOR {command} '
               f'TO {APP_ROLE} USING ({using})')
        if check is not None:
            sql += f' WITH CHECK ({check})'
    op.execute(sql)


def _drop_policy(name: str, table: str) -> None:
    op.execute(f'DROP POLICY IF EXISTS "{name}" ON "{table}"')


def _strict(table: str) -> None:
    """FOR ALL, user_id = CUR (USING + WITH CHECK)."""
    _policy(f"{table}_own", table, "ALL",
            f"user_id = {CUR}", f"user_id = {CUR}")


def _preauth_select(table: str, id_col: str = "user_id") -> None:
    """SELECT allows a missing context; every other op is strict."""
    _policy(f"{table}_select", table, "SELECT",
            f"{CUR} IS NULL OR {id_col} = {CUR}")
    _policy(f"{table}_insert", table, "INSERT", None,
            f"{id_col} = {CUR}")
    _policy(f"{table}_update", table, "UPDATE",
            f"{id_col} = {CUR}", f"{id_col} = {CUR}")
    _policy(f"{table}_delete", table, "DELETE",
            f"{id_col} = {CUR}")


def upgrade() -> None:
    if not _is_postgres():
        return
    for table in ALL_TABLES:
        _enable(table)

    # Strict tables (sync_jobs: INSERT/DELETE strict here; its
    # SELECT/UPDATE policies are the worker exception below).
    for table in STRICT_TABLES:
        if table == "sync_jobs":
            _policy("sync_jobs_insert", table, "INSERT", None,
                    f"user_id = {CUR}")
            _policy("sync_jobs_delete", table, "DELETE",
                    f"user_id = {CUR}")
        else:
            _strict(table)

    # Pre-auth SELECT exceptions.
    _preauth_select("users", id_col="id")
    for table in ("cf_accounts", "password_reset_tokens", "refresh_tokens"):
        _preauth_select(table)

    # users INSERT is permissive by design (registration creates the
    # row pre-auth); _preauth_select gave it a strict WITH CHECK, so
    # replace that policy with an open one.
    _drop_policy("users_insert", "users")
    _policy("users_insert", "users", "INSERT", None, "true")

    # sync_jobs: the worker claims jobs and recovers stale jobs with
    # no user context.
    _policy("sync_jobs_select", "sync_jobs", "SELECT",
            f"{CUR} IS NULL OR user_id = {CUR}")
    _policy("sync_jobs_update", "sync_jobs", "UPDATE",
            f"{CUR} IS NULL OR user_id = {CUR}",
            f"{CUR} IS NULL OR user_id = {CUR}")

    # problems: global shared catalog. Reads are open; writes need a
    # user context (sync and set_preference always run with one).
    _policy("problems_select", "problems", "SELECT", "true")
    _policy("problems_insert", "problems", "INSERT", None,
            f"{CUR} IS NOT NULL")
    _policy("problems_update", "problems", "UPDATE",
            f"{CUR} IS NOT NULL", f"{CUR} IS NOT NULL")
    _policy("problems_delete", "problems", "DELETE",
            f"{CUR} IS NOT NULL")

    # alembic_version: SELECT-only for the app role; migrations run as
    # owner (bypasses RLS), the app role must never write it.
    _policy("alembic_version_select", "alembic_version", "SELECT", "true")


def downgrade() -> None:
    if not _is_postgres():
        return
    for table in ALL_TABLES:
        for suffix in ("own", "select", "insert", "update", "delete"):
            _drop_policy(f"{table}_{suffix}", table)
    for table in ALL_TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
