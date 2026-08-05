"""merge_permissoes_tabela_e_bloco1_avaliacao

Revision ID: d3a41fddc68d
Revises: 7514970fac39, b56d36449c14
Create Date: 2026-08-05 15:58:48.080465

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3a41fddc68d'
down_revision: Union[str, Sequence[str], None] = ('7514970fac39', 'b56d36449c14')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
