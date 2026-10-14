"""caixa pode_criar_projeto_atalho

Revision ID: e1f3a7c9d204
Revises: d5a8b2c7e391
Create Date: 2026-10-13

O atalho "+ Novo projeto (atalho)" era decidido pelo cargo (diretor_projetos).
Vira caixa em `posicao_permissao`, marcada de saída só pra diretoria de
projetos, pra diretoria poder delegar sem mexer em código.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f3a7c9d204"
down_revision: Union[str, Sequence[str], None] = "d5a8b2c7e391"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_criar_projeto_atalho", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE posicao_permissao SET pode_criar_projeto_atalho = TRUE WHERE posicao = 'diretor_projetos'")


def downgrade() -> None:
    op.drop_column("posicao_permissao", "pode_criar_projeto_atalho")
