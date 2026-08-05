"""merge_tarefas_e_arquivado_projeto

Revision ID: 17d30a742ef6
Revises: 88728a91f918, fb72df6402d6
Create Date: 2026-08-04 20:20:52.900272

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '17d30a742ef6'
down_revision: Union[str, Sequence[str], None] = ('88728a91f918', 'fb72df6402d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
