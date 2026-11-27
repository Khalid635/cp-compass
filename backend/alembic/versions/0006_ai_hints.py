"""AI Hint Ladder cache table.

- ai_hints: one cached hint per (user, problem, step). The unique
  constraint is the cache key; the (user_id, created_at) index serves
  the daily-limit count.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_hints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("problem_id", sa.Integer(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("lang", sa.String(), nullable=False, server_default="en"),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"],
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "problem_id", "step"),
    )
    op.create_index("ix_ai_hints_user_created", "ai_hints",
                    ["user_id", "created_at"])

    op.create_table(
        "hint_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hint_usage_user_created", "hint_usage",
                    ["user_id", "created_at"])



def downgrade() -> None:
    op.drop_index("ix_hint_usage_user_created", table_name="hint_usage")
    op.drop_table("hint_usage")
    op.drop_index("ix_ai_hints_user_created", table_name="ai_hints")
    op.drop_table("ai_hints")
