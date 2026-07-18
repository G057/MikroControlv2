"""Add delayed and suppressible notification scheduling.

Revision ID: 20260717_04
Revises: 20260717_03
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260717_04"
down_revision = "20260717_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("available_after", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("suppressed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("suppression_reason", sa.String(length=80), nullable=True))
    op.add_column("notifications", sa.Column("telegram_required", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.create_index("ix_notifications_delivery_schedule", "notifications", ["suppressed_at", "available_after", "id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_delivery_schedule", table_name="notifications")
    op.drop_column("notifications", "suppression_reason")
    op.drop_column("notifications", "telegram_required")
    op.drop_column("notifications", "suppressed_at")
    op.drop_column("notifications", "available_after")
