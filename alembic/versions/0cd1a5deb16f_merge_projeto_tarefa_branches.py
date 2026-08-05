"""merge_projeto_tarefa_branches

Revision ID: 0cd1a5deb16f
Revises: 88728a91f918, fb72df6402d6
Create Date: 2026-08-05 09:55:19.218743

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0cd1a5deb16f'
down_revision: Union[str, Sequence[str], None] = ('88728a91f918', 'fb72df6402d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
