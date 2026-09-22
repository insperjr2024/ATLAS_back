"""remove_editar_juridico_marcar_assinado

Revision ID: e5d8a4c1f296
Revises: a3c7f92e6d18
Create Date: 2026-09-22 21:30:00.000000

⭐ 2026-09-22 — a pedido: tira `pode_editar_documento_juridico` e `pode_
marcar_documento_assinado`. Quem elabora/gerencia o contrato (diretoria ou
`pode_elaborar_contratos_proprios`/`pode_elaborar_qualquer_contrato`) já
podia gerar; agora também edita o texto livre pós-confirmação/regera e
marca como assinado — não precisava de uma caixa "Jurídico" à parte pra
cada ação. Só `diretor_projetos` tinha `pode_editar_documento_juridico`
marcada, e diretoria já tem a mesma capacidade via `eh_diretoria_de_
projetos` — sem dado relevante para migrar.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5d8a4c1f296'
down_revision: Union[str, Sequence[str], None] = 'a3c7f92e6d18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("posicao_permissao", "pode_editar_documento_juridico")
    op.drop_column("posicao_permissao", "pode_marcar_documento_assinado")


def downgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_editar_documento_juridico", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_marcar_documento_assinado", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
