"""pedido de entrada em banca

⭐ 2026-09-18, a pedido: a autoinscrição recusa quando a banca está no teto ou
a última vaga é reservada pro piso por frente que quem pede não cobre. Quem
quer entrar mesmo assim PEDE aqui, com justificativa; a diretoria decide na
aba Aprovações e a aprovação cria a candidatura, acima do teto normal. Mesmo
desenho de `banca_fora_janela_solicitacao`/`banca_remarcacao_solicitacao`.

Revision ID: a4d8e6f01c25
Revises: 97f768157452
Create Date: 2026-09-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4d8e6f01c25"
down_revision: Union[str, None] = "97f768157452"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "banca_entrada_solicitacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("banca_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("justificativa", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pendente", "aprovada", "recusada", name="status_entrada_banca"),
            server_default="pendente",
            nullable=False,
        ),
        sa.Column("respondido_por", sa.Integer(), nullable=True),
        sa.Column("resposta", sa.String(length=500), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("respondido_em", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["banca_id"], ["banca.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["respondido_por"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_banca_entrada_solicitacao_banca_id"),
        "banca_entrada_solicitacao",
        ["banca_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_banca_entrada_solicitacao_id"),
        "banca_entrada_solicitacao",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_banca_entrada_solicitacao_usuario_id"),
        "banca_entrada_solicitacao",
        ["usuario_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_banca_entrada_solicitacao_usuario_id"),
        table_name="banca_entrada_solicitacao",
    )
    op.drop_index(
        op.f("ix_banca_entrada_solicitacao_id"),
        table_name="banca_entrada_solicitacao",
    )
    op.drop_index(
        op.f("ix_banca_entrada_solicitacao_banca_id"),
        table_name="banca_entrada_solicitacao",
    )
    op.drop_table("banca_entrada_solicitacao")
    sa.Enum(name="status_entrada_banca").drop(op.get_bind(), checkfirst=True)
