"""initial_jul_2025

Revision ID: 5e97c112d05e
Revises: None
Create Date: 2025-06-30 21:38:14.268275

Create initial.sql from supabase
https://medium.com/@cemdurak/alembic-existing-db-a4cf36a33c77
pg_dump -h 127.0.0.1 -p 54322 -U postgres -O -s -n public -f initial.sql
- Remove any initial setup, any alter tables, alembic create/alters
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e97c112d05e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    with open('alembic/initial.sql') as file:
        op.execute(file.read())

def downgrade() -> None:
    pass
