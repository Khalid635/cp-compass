"""Public profile opt-in flag (batch 5).

- users.public_profile: Boolean NOT NULL DEFAULT FALSE. Default OFF:
  nobody is public unless they choose it (GET /api/v1/u/{handle}
  404s for private handles).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("public_profile", sa.Boolean(),
                                     nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "public_profile")
