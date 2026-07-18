"""Add per-user session timeout configuration.

Revision ID: 20260717_03
Revises: 20260716_02
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260717_03"
down_revision = "20260716_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "session_timeout_minutes" not in columns:
        op.add_column("users", sa.Column("session_timeout_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "session_timeout_minutes")
