"""Add channel eligibility flag to existing notification schedules.

Revision ID: 20260717_05
Revises: 20260717_04
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260717_05"
down_revision = "20260717_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("notifications")}
    if "telegram_required" not in columns:
        op.add_column("notifications", sa.Column("telegram_required", sa.Boolean(), nullable=False, server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("notifications", "telegram_required")
