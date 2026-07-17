"""Reconcile indexes, timestamps, and alert event references from pre-Alembic databases.

Revision ID: 20260716_02
Revises: 20260716_01
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260716_02"
down_revision = "20260716_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Legacy runtime DDL created these columns without timezone information.
    # Application timestamps have always been normalized to UTC before storage.
    for table, column in (
        ("alerts", "first_seen"),
        ("alerts", "last_seen"),
        ("event_logs", "received_timestamp"),
        ("event_logs", "event_timestamp"),
    ):
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE TIMESTAMP WITH TIME ZONE USING {column} AT TIME ZONE 'UTC'"
        )

    orphan_opening = bind.execute(sa.text(
        "SELECT count(*) FROM alerts a LEFT JOIN event_logs e ON e.id = a.opening_event_id "
        "WHERE a.opening_event_id IS NOT NULL AND e.id IS NULL"
    )).scalar_one()
    orphan_resolution = bind.execute(sa.text(
        "SELECT count(*) FROM alerts a LEFT JOIN event_logs e ON e.id = a.resolution_event_id "
        "WHERE a.resolution_event_id IS NOT NULL AND e.id IS NULL"
    )).scalar_one()
    if orphan_opening or orphan_resolution:
        raise RuntimeError(
            "No se pueden crear claves foráneas de alerts: existen referencias a eventos inexistentes "
            f"(apertura={orphan_opening}, resolución={orphan_resolution})."
        )

    foreign_key_columns = {tuple(fk["constrained_columns"]) for fk in sa.inspect(bind).get_foreign_keys("alerts")}
    if ("opening_event_id",) not in foreign_key_columns:
        op.create_foreign_key("fk_alerts_opening_event", "alerts", "event_logs", ["opening_event_id"], ["id"])
    if ("resolution_event_id",) not in foreign_key_columns:
        op.create_foreign_key("fk_alerts_resolution_event", "alerts", "event_logs", ["resolution_event_id"], ["id"])

    op.execute("CREATE INDEX IF NOT EXISTS ix_event_logs_source ON event_logs(source)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_logs_event_type ON event_logs(event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_logs_correlation_id ON event_logs(correlation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_logs_received_timestamp ON event_logs(received_timestamp)")


def downgrade() -> None:
    raise RuntimeError("La reconciliación de esquema no puede revertirse automáticamente.")
