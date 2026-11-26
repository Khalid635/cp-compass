"""Phase 2: weekly practice goal on users + old rating on rating_history.

- users.weekly_goal: problems to solve per week (default 5), set in Settings.
- rating_history.old_rating: the rating before the contest, so contest
  auto-analysis can show the exact rating change without chaining.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("weekly_goal", sa.Integer(), nullable=False,
                                     server_default="5"))
    op.add_column("rating_history", sa.Column("old_rating", sa.Integer(),
                                              nullable=True))


def downgrade() -> None:
    op.drop_column("rating_history", "old_rating")
    op.drop_column("users", "weekly_goal")
