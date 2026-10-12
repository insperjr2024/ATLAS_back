"""comunicados manuais por segmento

Revision ID: b8e4c2a6d930
Revises: a7d3e9f1c852
Create Date: 2026-10-11

Tres coisas do mesmo pedido (a diretoria manda e-mail pra um recorte de
pessoas, tipo "quem esta com 0 bancas"):

- tipo `comunicado` em `tipo_notificacao`;
- caixa `pode_enviar_comunicados` em `posicao_permissao`, marcada de saida
  pros tres cargos de diretoria;
- `notificacao.corpo` passa de VARCHAR(500) pra TEXT: a mensagem de um
  comunicado e escrita a mao e nao cabe em 500 caracteres.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8e4c2a6d930"
down_revision: Union[str, Sequence[str], None] = "a7d3e9f1c852"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIRETORIA = ("diretor_projetos", "diretor_pessoas", "diretor")


def upgrade() -> None:
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_enviar_comunicados", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        sa.text(
            "UPDATE posicao_permissao SET pode_enviar_comunicados = TRUE WHERE posicao IN :posicoes"
        ).bindparams(sa.bindparam("posicoes", expanding=True, value=list(DIRETORIA)))
    )
    op.alter_column(
        "notificacao",
        "corpo",
        type_=sa.Text(),
        existing_type=sa.String(500),
        existing_nullable=True,
    )
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS 'comunicado'")


def downgrade() -> None:
    op.alter_column(
        "notificacao",
        "corpo",
        type_=sa.String(500),
        existing_type=sa.Text(),
        existing_nullable=True,
    )
    op.drop_column("posicao_permissao", "pode_enviar_comunicados")
