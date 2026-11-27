"""Batch 1 security (audit F1/F2/F5/F6).

- users.email_verified / users.totp_enabled / users.last_retrain_at.
  Existing accounts are backfilled email_verified=True — they predate
  verification (dev DB only; the one real account was created by its
  owner before this change).
- New tables: email_verifications, totp_secrets, backup_codes,
  handle_verifications.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified", sa.Boolean(),
                                     nullable=False, server_default="0"))
    op.add_column("users", sa.Column("totp_enabled", sa.Boolean(),
                                     nullable=False, server_default="0"))
    op.add_column("users", sa.Column("last_retrain_at", sa.DateTime(),
                                     nullable=True))
    # Accounts created before email verification existed are grandfathered.
    op.execute("UPDATE users SET email_verified = 1")

    op.create_table(
        "email_verifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_verifications_user_id", "email_verifications",
                    ["user_id"])

    op.create_table(
        "totp_secrets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("secret_encrypted", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_totp_secrets_user_id", "totp_secrets", ["user_id"])

    op.create_table(
        "backup_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_codes_user_id", "backup_codes", ["user_id"])
    op.create_index("ix_backup_codes_code_hash", "backup_codes", ["code_hash"])

    op.create_table(
        "handle_verifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("handle", sa.String(), nullable=False),
        sa.Column("handle_norm", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_handle_verifications_user_id", "handle_verifications",
                    ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_handle_verifications_user_id", table_name="handle_verifications")
    op.drop_table("handle_verifications")
    op.drop_index("ix_backup_codes_code_hash", table_name="backup_codes")
    op.drop_index("ix_backup_codes_user_id", table_name="backup_codes")
    op.drop_table("backup_codes")
    op.drop_index("ix_totp_secrets_user_id", table_name="totp_secrets")
    op.drop_table("totp_secrets")
    op.drop_index("ix_email_verifications_user_id", table_name="email_verifications")
    op.drop_table("email_verifications")
    op.drop_column("users", "last_retrain_at")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "email_verified")
