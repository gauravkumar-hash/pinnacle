"""add_service_availability_fields

Revision ID: c0d1e2f3a4b5
Revises: f9a1b2c3d4e5
Create Date: 2026-04-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c0d1e2f3a4b5'
down_revision: Union[str, None] = '59fe9ecf4385'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('services', sa.Column('available_days', sa.String(), nullable=True))
    op.add_column('services', sa.Column('available_time_slots', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('services', 'available_time_slots')
    op.drop_column('services', 'available_days')
