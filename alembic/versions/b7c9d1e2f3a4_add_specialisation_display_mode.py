"""add specialisation display mode

Revision ID: b7c9d1e2f3a4
Revises: a0c0453f17a3
Create Date: 2026-06-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c9d1e2f3a4"
down_revision: Union[str, None] = "a0c0453f17a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "specialisations",
        sa.Column("display_mode", sa.String(), nullable=False, server_default="doctors"),
    )
    op.alter_column("specialisations", "display_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("specialisations", "display_mode")
