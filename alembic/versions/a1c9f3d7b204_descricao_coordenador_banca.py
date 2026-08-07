"""descricao_coordenador_banca

Revision ID: a1c9f3d7b204
Revises: 5f69087982a7
Create Date: 2026-08-06 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c9f3d7b204'
down_revision: Union[str, Sequence[str], None] = '5f69087982a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('banca', sa.Column('descricao_coordenador', sa.Text(), nullable=True))
    op.add_column('banca', sa.Column('descricao_coordenador_enviada_em', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('banca', 'descricao_coordenador_enviada_em')
    op.drop_column('banca', 'descricao_coordenador')
