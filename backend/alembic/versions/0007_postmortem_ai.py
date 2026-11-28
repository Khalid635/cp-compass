"""Contest post-mortem AI cache tables.

- postmortem_analysis: one cached Gemini analysis per (user, contest).
  The unique constraint is the cache key; the (user_id, created_at)
  index serves the daily-limit count.
- postmortem_usage: one row per generation (cache hits insert nothing).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "postmortem_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("contest_id", sa.Integer(), nullable=False),
        sa.Column("lang", sa.String(), nullable=False, server_default="en"),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "contest_id"),
    )
    op.create_index("ix_postmortem_analysis_user_created", "postmortem_analysis",
                    ["user_id", "created_at"])

    op.create_table(
        "postmortem_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("contest_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_postmortem_usage_user_created", "postmortem_usage",
                    ["user_id", "created_at"])



def downgrade() -> None:
    op.drop_index("ix_postmortem_usage_user_created", table_name="postmortem_usage")
    op.drop_table("postmortem_usage")
    op.drop_index("ix_postmortem_analysis_user_created", table_name="postmortem_analysis")
    op.drop_table("postmortem_analysis")
