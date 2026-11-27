"""Batch 2: failure-pattern analysis.

- submissions.passed_test_count (nullable): tests passed before the
  verdict, from Codeforces user.status. NULL on rows synced before
  this column existed — the sync backfill (app.sync) fills them.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("passed_test_count", sa.Integer(),
                                           nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "passed_test_count")
