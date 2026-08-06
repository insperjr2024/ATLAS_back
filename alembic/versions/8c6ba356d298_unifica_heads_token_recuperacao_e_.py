"""unifica heads token recuperacao e escopos de banca

Revision ID: 8c6ba356d298
Revises: a9267ae28eeb, c41a7b90e5d2
Create Date: 2026-08-06 00:05:23.911896

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c6ba356d298'
down_revision: Union[str, Sequence[str], None] = ('a9267ae28eeb', 'c41a7b90e5d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
