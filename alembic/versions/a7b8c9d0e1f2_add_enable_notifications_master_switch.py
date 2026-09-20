"""add enable_notifications master switch to patient notification preferences

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-09-20

Adds:
  - patient_notification_preferences.enable_notifications

The patient-facing master switch: false means send this patient NOTHING - no appointment
reminders, no health-report alerts, no marketing. `marketing_opt_in` remains the narrower
switch governing marketing / health-info blasts only.

Default is TRUE, deliberately: every patient who exists today keeps receiving exactly what
they receive now, and the backfill is free via the server default.

NOTE: this is NOT PinnacleAccount.enable_notifications (models/pinnacle.py), which governs
STAFF / doctor notifications and defaults to false. Same column name, different table,
different audience. Do not consolidate them.

Enforced in utils/notifications.py::send_patient_notification, which every patient push goes
through. Teleconsult session-start notifications pass bypass_preferences=True so a patient who
muted notifications still learns their doctor has joined the call.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "patient_notification_preferences",
        sa.Column(
            "enable_notifications",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("patient_notification_preferences", "enable_notifications")
