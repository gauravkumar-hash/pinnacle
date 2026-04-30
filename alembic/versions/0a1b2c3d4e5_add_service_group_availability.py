"""Add available_days and available_time_slots to appointment_service_groups

Revision ID: 0a1b2c3d4e5
Revises: f9a1b2c3d4e5
Create Date: 2026-04-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a1b2c3d4e5'
down_revision: Union[str, None] = 'f9a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'appointment_service_groups',
        sa.Column(
            'available_days',
            sa.ARRAY(sa.String(), dimensions=1),
            nullable=False,
            server_default='{}'
        )
    )
    op.add_column(
        'appointment_service_groups',
        sa.Column(
            'available_time_slots',
            sa.ARRAY(sa.String(), dimensions=1),
            nullable=False,
            server_default='{}'
        )
    )


def downgrade() -> None:
    op.drop_column('appointment_service_groups', 'available_time_slots')
    op.drop_column('appointment_service_groups', 'available_days')
