"""add clinic/corporate slot allocation (also merges the two existing heads)

Revision ID: c3d4e5f6a7b8
Revises: 7c1e9a2b4d10, b1c2d3e4f5a6
Create Date: 2026-10-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = ('7c1e9a2b4d10', 'b1c2d3e4f5a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # All nullable: NULL keeps today's behaviour (only max_bookings applies)
    op.add_column('appointment_operating_hours', sa.Column('max_clinic_bookings', sa.Integer(), nullable=True))
    op.add_column('appointment_operating_hours', sa.Column('max_corporate_bookings', sa.Integer(), nullable=True))
    op.add_column('appointment_corporate_codes', sa.Column('max_bookings_per_slot', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('appointment_corporate_codes', 'max_bookings_per_slot')
    op.drop_column('appointment_operating_hours', 'max_corporate_bookings')
    op.drop_column('appointment_operating_hours', 'max_clinic_bookings')
