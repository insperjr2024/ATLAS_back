"""merge heads apos pull de origin main

Revision ID: 69ba067294f8
Revises: 1091404c813d, c7a2e5f91b3d
Create Date: 2026-08-07 01:05:38.649879

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69ba067294f8'
down_revision: Union[str, Sequence[str], None] = ('1091404c813d', 'c7a2e5f91b3d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
