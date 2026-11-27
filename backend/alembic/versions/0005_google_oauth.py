"""Google OAuth sign-in.

- users.google_id (nullable, unique): the Google `sub` claim, set when
  an account signs in with Google or links a Google account.
- users.password_hash becomes nullable: Google-only accounts have no
  password. batch_alter_table so the ALTER works on SQLite (dev) as
  well as Postgres (prod).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_id", sa.String(), nullable=True))
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(),
                              nullable=True)
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_id", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(),
                              nullable=False)
    op.drop_column("users", "google_id")
