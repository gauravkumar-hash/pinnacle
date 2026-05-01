"""merge_heads

Revision ID: 62aa7e4fa49f
Revises: 0a1b2c3d4e5, c0d1e2f3a4b5
Create Date: 2026-05-01 12:40:17.594165

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62aa7e4fa49f'
down_revision: Union[str, None] = ('0a1b2c3d4e5', 'c0d1e2f3a4b5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
