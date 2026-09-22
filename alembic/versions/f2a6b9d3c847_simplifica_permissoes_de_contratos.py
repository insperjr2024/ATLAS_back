"""simplifica_permissoes_de_contratos

Revision ID: f2a6b9d3c847
Revises: d4e7b8c1a293
Create Date: 2026-09-22 12:00:00.000000

⭐ 2026-09-22 — a pedido: simplifica o catálogo de permissões de Contratos.

Tira `pode_gerar_documento_juridico` (diretoria já gera via `eh_diretoria_
de_projetos`, ninguém tinha marcado), `pode_ver_painel_contratos` (mesma
coisa — a aba já é visível por diretoria/Jurídico/vendedor/coordenador/
`pode_elaborar_*` sem esta caixa) e `pode_ver_repositorio_contratos`
(diretoria já vê via `eh_diretoria_de_projetos`, o resto do catálogo não
usava). Nenhuma posição tinha qualquer uma das três marcada — sem dado
para migrar.

Cria `pode_aprovar_contrato_internamente`, separada de `pode_editar_
documento_juridico`: antes a aprovação jurídica (fechar a revisão interna)
morava dentro da caixa de editar; agora é a sua própria caixa.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2a6b9d3c847'
down_revision: Union[str, Sequence[str], None] = 'd4e7b8c1a293'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_aprovar_contrato_internamente", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_column("posicao_permissao", "pode_gerar_documento_juridico")
    op.drop_column("posicao_permissao", "pode_ver_painel_contratos")
    op.drop_column("posicao_permissao", "pode_ver_repositorio_contratos")


def downgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_gerar_documento_juridico", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_ver_painel_contratos", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_ver_repositorio_contratos", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_column("posicao_permissao", "pode_aprovar_contrato_internamente")
