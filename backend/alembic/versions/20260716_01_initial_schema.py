"""Create the MikroControl baseline schema.

Revision ID: 20260716_01
Revises:
Create Date: 2026-07-16

Existing deployments must be checked and stamped at this revision before the
application is upgraded. See deploy/install-ubuntu.md.
"""

from alembic import op

from app.core.database import Base
import app.models  # Register the complete schema for a new installation.


revision = "20260716_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    raise RuntimeError("The baseline schema migration cannot be downgraded automatically.")
