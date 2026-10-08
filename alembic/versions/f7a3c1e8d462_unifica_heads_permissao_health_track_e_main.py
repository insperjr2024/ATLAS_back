"""unifica heads: caixa do Health Track com a main (sabatina, arquivo de contratos)

`e9c2a5d7b413` (caixa `pode_ver_health_track`) saiu de `d1b8f4a6e372` enquanto
a main seguia por outro caminho até `c9f1b3e7a526`, deixando duas heads. As
colunas novas da main em `posicao_permissao` são outras, então esta revisão só
junta as pontas.

Revision ID: f7a3c1e8d462
Revises: c9f1b3e7a526, e9c2a5d7b413
Create Date: 2026-10-07 18:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'f7a3c1e8d462'
down_revision: Union[str, Sequence[str], None] = ('c9f1b3e7a526', 'e9c2a5d7b413')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
