"""add opened_at to campaign recipients (notification tap tracking)

Revision ID: 7c1e9a2b4d10
Revises: a7b8c9d0e1f2
Create Date: 2026-10-13

Nullable column, no default, no backfill: safe to run on the live table.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7c1e9a2b4d10"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "backend_notification_campaign_recipients",
        sa.Column("opened_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("backend_notification_campaign_recipients", "opened_at")
