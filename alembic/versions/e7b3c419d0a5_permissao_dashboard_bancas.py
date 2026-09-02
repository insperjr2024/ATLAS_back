"""permissao_dashboard_bancas

Revision ID: e7b3c419d0a5
Revises: d1f4a7c88b52
Create Date: 2026-09-01

A 14ª caixa de `posicao_permissao`: `pode_ver_dashboard_bancas`.

O Dashboard Bancas (`/avaliacoes` — notas por pergunta, histórico de bancas e
os formulários de banca) nunca esteve nesta tabela. Ele era travado em
`diretor_projetos` por uma matriz do FRONT (`utils/permissoes.ts`) somada a
`require_diretor_projetos` nas rotas — ou seja, delegar a leitura das notas
exigia promover a pessoa a diretora de projetos inteira, com tudo o que isso
carrega junto.

⭐ **A migration não muda o comportamento de ninguém.** A coluna nasce `false`
para todas as posições e é ligada só em `diretor_projetos`, que é exatamente
quem enxergava o dashboard até aqui. Quem quiser delegar liga a caixa em
Configurações depois — que é o ponto de a caixa existir.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7b3c419d0a5'
down_revision: Union[str, Sequence[str], None] = 'd1f4a7c88b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUNA = 'pode_ver_dashboard_bancas'


def upgrade() -> None:
    op.add_column(
        'posicao_permissao',
        sa.Column(COLUNA, sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Preserva quem já via: só o diretor de projetos. Escrito como UPDATE
    # parametrizado (e não string interpolada) para valer igual no Postgres e
    # no MySQL, como o resto das migrations desta base.
    tabela = sa.table(
        'posicao_permissao',
        sa.column('posicao', sa.String),
        sa.column(COLUNA, sa.Boolean),
    )
    op.execute(
        tabela.update()
        .where(tabela.c.posicao == op.inline_literal('diretor_projetos'))
        .values(**{COLUNA: True})
    )


def downgrade() -> None:
    op.drop_column('posicao_permissao', COLUNA)
