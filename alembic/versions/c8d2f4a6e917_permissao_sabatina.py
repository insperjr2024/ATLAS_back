"""caixa "acessar configurações de sabatina"

Revision ID: c8d2f4a6e917
Revises: b2c6e9d1a473
Create Date: 2026-10-06

A pedido: a Configuração de Sabatina deixa de ser amarrada à posição e
vira caixa de permissão, marcada de saída pros três cargos de diretoria.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8d2f4a6e917"
down_revision: Union[str, Sequence[str], None] = "b2c6e9d1a473"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIRETORIA = ("diretor_projetos", "diretor_pessoas", "diretor")


def upgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_acessar_configuracoes_sabatina", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        sa.text(
            "UPDATE posicao_permissao SET pode_acessar_configuracoes_sabatina = TRUE WHERE posicao IN :posicoes"
        ).bindparams(sa.bindparam("posicoes", expanding=True, value=list(DIRETORIA)))
    )


def downgrade() -> None:
    op.drop_column("posicao_permissao", "pode_acessar_configuracoes_sabatina")
