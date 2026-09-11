"""add_reschedule_reason_to_appointment_requests

Revision ID: b1c2d3e4f5a6
Revises: 9f0a1b2c3d4e
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '9f0a1b2c3d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointment_requests",
        sa.Column("reschedule_reason", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("appointment_requests", "reschedule_reason")
