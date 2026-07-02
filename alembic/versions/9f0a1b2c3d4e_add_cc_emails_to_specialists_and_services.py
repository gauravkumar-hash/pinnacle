"""add cc_emails to specialists and services

Revision ID: 9f0a1b2c3d4e
Revises: b7c9d1e2f3a4
Create Date: 2026-07-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '9f0a1b2c3d4e'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('specialists', sa.Column('cc_emails', sa.JSON(), nullable=True))
    op.add_column('services', sa.Column('cc_emails', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('specialists', 'cc_emails')
    op.drop_column('services', 'cc_emails')
