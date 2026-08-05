"""merge_bloco1_avaliacao_e_permissoes_desempenho

Revision ID: b56d36449c14
Revises: 0351b6185bf1, 0aa4dd79044f
Create Date: 2026-08-05 15:48:51.116954

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b56d36449c14'
down_revision: Union[str, Sequence[str], None] = ('0351b6185bf1', '0aa4dd79044f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
