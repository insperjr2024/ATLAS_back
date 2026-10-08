"""permissao_ver_health_track

Revision ID: e9c2a5d7b413
Revises: d1b8f4a6e372
Create Date: 2026-10-07 12:00:00.000000

2026-10-07 — a pedido: o Health Track passa a ser visível só para o diretor
de projetos. Até aqui qualquer um que enxergasse o projeto via a aba, e
qualquer um com acesso a Configurações via a regra do status geral.

Vira caixa (`pode_ver_health_track`) em vez de guarda por posição para dar
acesso a outras posições depois, pela tela de Configurações, sem código.

A coluna nasce `false` para todas as posições e é ligada só em
`diretor_projetos`. Cargo criado pela tela também nasce sem ela.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e9c2a5d7b413'
down_revision: Union[str, Sequence[str], None] = 'd1b8f4a6e372'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUNA = 'pode_ver_health_track'


def upgrade() -> None:
    op.add_column(
        'posicao_permissao',
        sa.Column(COLUNA, sa.Boolean(), nullable=False, server_default=sa.false()),
    )
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
