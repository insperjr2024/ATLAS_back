"""remove_importar_documento_antigo

Revision ID: f8b3c6d0a417
Revises: e5d8a4c1f296
Create Date: 2026-09-22 22:00:00.000000

⭐ 2026-09-22 — a pedido: tira `pode_importar_documento_antigo`. A caixa
nunca teve nenhuma funcionalidade por trás (nenhum endpoint/use case a
usava) — nasceu junto com o resto do catálogo de Contratos mas a feature
de importar um documento antigo nunca foi construída. Nenhuma posição
tinha esta marcada.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f8b3c6d0a417'
down_revision: Union[str, Sequence[str], None] = 'e5d8a4c1f296'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("posicao_permissao", "pode_importar_documento_antigo")


def downgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_importar_documento_antigo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
