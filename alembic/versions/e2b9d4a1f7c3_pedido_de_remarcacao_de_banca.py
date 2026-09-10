"""pedido de remarcação de banca

⭐ 2026-09-10, a pedido: remarcar banca com data já marcada deixa de ser livre
para quem edita o projeto. Quem não é da diretoria PEDE aqui, com
justificativa; a diretoria decide na aba Aprovações e a aprovação já remarca a
banca. Mesmo desenho de `banca_fora_janela_solicitacao`.

Revision ID: e2b9d4a1f7c3
Revises: c5e1a92f7b34
Create Date: 2026-09-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b9d4a1f7c3"
down_revision: Union[str, None] = "c5e1a92f7b34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "banca_remarcacao_solicitacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("banca_id", sa.Integer(), nullable=False),
        sa.Column("projeto_escopo_id", sa.Integer(), nullable=False),
        sa.Column("data_hora_anterior", sa.DateTime(), nullable=False),
        sa.Column("data_hora_pretendida", sa.DateTime(), nullable=False),
        sa.Column("justificativa", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pendente", "aprovada", "recusada", name="status_remarcacao_banca"),
            server_default="pendente",
            nullable=False,
        ),
        sa.Column("solicitado_por", sa.Integer(), nullable=False),
        sa.Column("respondido_por", sa.Integer(), nullable=True),
        sa.Column("resposta", sa.String(length=500), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("respondido_em", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["banca_id"], ["banca.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["projeto_escopo_id"], ["projeto_escopo.id"]),
        sa.ForeignKeyConstraint(["respondido_por"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["solicitado_por"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_banca_remarcacao_solicitacao_banca_id"),
        "banca_remarcacao_solicitacao",
        ["banca_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_banca_remarcacao_solicitacao_data_hora_pretendida"),
        "banca_remarcacao_solicitacao",
        ["data_hora_pretendida"],
        unique=False,
    )
    op.create_index(
        op.f("ix_banca_remarcacao_solicitacao_id"),
        "banca_remarcacao_solicitacao",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_banca_remarcacao_solicitacao_projeto_escopo_id"),
        "banca_remarcacao_solicitacao",
        ["projeto_escopo_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_banca_remarcacao_solicitacao_projeto_escopo_id"),
        table_name="banca_remarcacao_solicitacao",
    )
    op.drop_index(
        op.f("ix_banca_remarcacao_solicitacao_id"),
        table_name="banca_remarcacao_solicitacao",
    )
    op.drop_index(
        op.f("ix_banca_remarcacao_solicitacao_data_hora_pretendida"),
        table_name="banca_remarcacao_solicitacao",
    )
    op.drop_index(
        op.f("ix_banca_remarcacao_solicitacao_banca_id"),
        table_name="banca_remarcacao_solicitacao",
    )
    op.drop_table("banca_remarcacao_solicitacao")
    sa.Enum(name="status_remarcacao_banca").drop(op.get_bind(), checkfirst=True)
