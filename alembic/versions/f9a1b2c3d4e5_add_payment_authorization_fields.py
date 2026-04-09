"""add_payment_authorization_fields

Revision ID: f9a1b2c3d4e5
Revises: e1f2a3b4c5d6
Create Date: 2026-04-08 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f9a1b2c3d4e5'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum values for PaymentStatus
    # Note: PostgreSQL requires special handling for enum types
    op.execute("""
        ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'payment_authorized';
    """)
    op.execute("""
        ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'payment_capture_pending';
    """)
    op.execute("""
        ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS 'payment_captured';
    """)
    
    # Add new columns to payment_logs table
    op.add_column('payment_logs',
        sa.Column('authorized_amount', sa.Float(), nullable=True,
                  comment='Amount authorized (held) on payment method')
    )
    op.add_column('payment_logs',
        sa.Column('captured_amount', sa.Float(), nullable=True,
                  comment='Amount actually captured/charged from authorized amount')
    )
    op.add_column('payment_logs',
        sa.Column('authorization_id', sa.String(), nullable=True,
                  comment='Payment gateway authorization/transaction ID')
    )
    op.add_column('payment_logs',
        sa.Column('authorization_expires_at', sa.DateTime(), nullable=True,
                  comment='Timestamp when authorization expires')
    )
    op.add_column('payment_logs',
        sa.Column('capture_attempted_at', sa.DateTime(), nullable=True,
                  comment='Timestamp when capture was attempted')
    )
    
    # Create index on authorization_expires_at for cleanup jobs
    op.create_index('idx_payment_logs_auth_expires',
                    'payment_logs',
                    ['authorization_expires_at'],
                    postgresql_where=sa.text("authorization_expires_at IS NOT NULL"))


def downgrade() -> None:
    # Drop index
    op.drop_index('idx_payment_logs_auth_expires', table_name='payment_logs')
    
    # Drop columns
    op.drop_column('payment_logs', 'capture_attempted_at')
    op.drop_column('payment_logs', 'authorization_expires_at')
    op.drop_column('payment_logs', 'authorization_id')
    op.drop_column('payment_logs', 'captured_amount')
    op.drop_column('payment_logs', 'authorized_amount')
    
    # Note: Cannot easily remove enum values in PostgreSQL
    # They will remain but won't be used after downgrade
