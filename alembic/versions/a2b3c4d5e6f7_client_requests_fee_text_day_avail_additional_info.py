"""client_requests_fee_text_day_avail_additional_info

Revision ID: a2b3c4d5e6f7
Revises: b7c9d1e2f3a4
Create Date: 2026-07-01 00:00:00.000000

Changes:
- services.consultation_fee: Integer -> VARCHAR (supports text ranges e.g. "$50 - $100")
- specialists.consultation_fee: Integer -> VARCHAR
- services.day_availability: new JSON column (per-day AM/PM control)
- specialists.day_availability: new JSON column
- appointment_requests.additional_info: new VARCHAR column (patient extra notes)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'b7c9d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change consultation_fee from numeric to text in services
    op.alter_column(
        'services', 'consultation_fee',
        existing_type=sa.Integer(),
        type_=sa.String(),
        existing_nullable=True,
        postgresql_using='consultation_fee::VARCHAR',
    )

    # Change consultation_fee from numeric to text in specialists
    op.alter_column(
        'specialists', 'consultation_fee',
        existing_type=sa.Integer(),
        type_=sa.String(),
        existing_nullable=True,
        postgresql_using='consultation_fee::VARCHAR',
    )

    # Add per-day AM/PM availability JSON column to services
    op.add_column('services', sa.Column('day_availability', sa.JSON(), nullable=True))

    # Add per-day AM/PM availability JSON column to specialists
    op.add_column('specialists', sa.Column('day_availability', sa.JSON(), nullable=True))

    # Add additional_info text field to appointment_requests
    op.add_column('appointment_requests', sa.Column('additional_info', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('appointment_requests', 'additional_info')
    op.drop_column('specialists', 'day_availability')
    op.drop_column('services', 'day_availability')

    op.alter_column(
        'specialists', 'consultation_fee',
        existing_type=sa.String(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="NULLIF(regexp_replace(consultation_fee, '[^0-9]', '', 'g'), '')::INTEGER",
    )

    op.alter_column(
        'services', 'consultation_fee',
        existing_type=sa.String(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="NULLIF(regexp_replace(consultation_fee, '[^0-9]', '', 'g'), '')::INTEGER",
    )
