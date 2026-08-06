"""merge_banca_varios_escopos_e_recuperacao_senha

Revision ID: 1f4ca90bfbbb
Revises: a9267ae28eeb, c41a7b90e5d2
Create Date: 2026-08-05 18:15:53.120843

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f4ca90bfbbb'
down_revision: Union[str, Sequence[str], None] = ('a9267ae28eeb', 'c41a7b90e5d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
