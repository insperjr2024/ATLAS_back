"""permissoes_identidade_e_elaborar_contratos

Revision ID: d4e7b8c1a293
Revises: 9c1e5a7d3f42
Create Date: 2026-09-22 10:00:00.000000

⭐ 2026-09-22 — a pedido: três caixas novas em `posicao_permissao`.

`pode_editar_identidade_institucional` delega o que era hardcoded pra
diretoria de projetos (`eh_diretoria_de_projetos`). `pode_elaborar_
contratos_proprios` e `pode_elaborar_qualquer_contrato` abrem a aba
Contratos e o direito de elaborar (abrir/preencher/confirmar/gerar) um
documento jurídico pra quem não é diretoria/Jurídico — a primeira só nos
projetos em que a pessoa é vendedora, a segunda em qualquer um.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e7b8c1a293'
down_revision: Union[str, Sequence[str], None] = '9c1e5a7d3f42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_editar_identidade_institucional", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_elaborar_contratos_proprios", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_elaborar_qualquer_contrato", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("posicao_permissao", "pode_elaborar_qualquer_contrato")
    op.drop_column("posicao_permissao", "pode_elaborar_contratos_proprios")
    op.drop_column("posicao_permissao", "pode_editar_identidade_institucional")
