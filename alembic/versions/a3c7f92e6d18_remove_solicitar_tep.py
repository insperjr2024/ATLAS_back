"""remove_solicitar_tep

Revision ID: a3c7f92e6d18
Revises: c9d1e3f5a728
Create Date: 2026-09-22 21:00:00.000000

⭐ 2026-09-22 — a pedido: tira `pode_solicitar_tep`. Abrir um TEP já cai nas
mesmas caixas que abrem qualquer outro documento jurídico (diretoria,
`pode_editar_documento_juridico`, `pode_elaborar_contratos_proprios`/
`pode_elaborar_qualquer_contrato`) — não precisava de uma caixa própria.
Nenhuma posição tinha esta marcada — sem dado para migrar.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3c7f92e6d18'
down_revision: Union[str, Sequence[str], None] = 'c9d1e3f5a728'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("posicao_permissao", "pode_solicitar_tep")


def downgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_solicitar_tep", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
