"""add_appointment_quota_controls

Revision ID: e1f2a3b4c5d6
Revises: d44af2046d9c
Create Date: 2026-04-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd44af2046d9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add max_appointments_per_session to appointment_operating_hours
    op.add_column('appointment_operating_hours', 
        sa.Column('max_appointments_per_session', sa.Integer(), nullable=True))
    
    # Add appointment quota fields to appointment_corporate_codes
    op.add_column('appointment_corporate_codes', 
        sa.Column('max_appointments_total', sa.Integer(), nullable=True))
    op.add_column('appointment_corporate_codes', 
        sa.Column('max_appointments_per_day', sa.Integer(), nullable=True))
    
    # Create new table for tracking corporate code quota usage
    op.create_table('appointment_corporate_quota_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('corporate_code_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('appointments_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['corporate_code_id'], ['appointment_corporate_codes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_appointment_corporate_quota_usage_corporate_code_id'), 
        'appointment_corporate_quota_usage', ['corporate_code_id'], unique=False)
    op.create_index(op.f('ix_appointment_corporate_quota_usage_date'), 
        'appointment_corporate_quota_usage', ['date'], unique=False)


def downgrade() -> None:
    # Drop indexes and table
    op.drop_index(op.f('ix_appointment_corporate_quota_usage_date'), 
        table_name='appointment_corporate_quota_usage')
    op.drop_index(op.f('ix_appointment_corporate_quota_usage_corporate_code_id'), 
        table_name='appointment_corporate_quota_usage')
    op.drop_table('appointment_corporate_quota_usage')
    
    # Remove columns from appointment_corporate_codes
    op.drop_column('appointment_corporate_codes', 'max_appointments_per_day')
    op.drop_column('appointment_corporate_codes', 'max_appointments_total')
    
    # Remove column from appointment_operating_hours
    op.drop_column('appointment_operating_hours', 'max_appointments_per_session')
