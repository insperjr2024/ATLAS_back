"""merge heads apos pull de origin main

Revision ID: c3993055bd44
Revises: 69ba067294f8, 9ef5e8c8a983
Create Date: 2026-08-07 01:54:59.209754

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3993055bd44'
down_revision: Union[str, Sequence[str], None] = ('69ba067294f8', '9ef5e8c8a983')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
