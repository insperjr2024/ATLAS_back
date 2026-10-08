"""health track: rodadas de avaliação

Revision ID: a4d8e2c6f931
Revises: f7a3c1e8d462
Create Date: 2026-10-08

Ver `models/health_track_rodada_model.py`: a diretoria abre uma rodada, que
congela os projetos em acompanhamento, e cada um precisa ser avaliado ou
ter a falta justificada antes de a rodada concluir.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4d8e2c6f931"
down_revision: Union[str, Sequence[str], None] = "f7a3c1e8d462"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SITUACAO = sa.Enum("pendente", "avaliada", "justificada", name="situacao_health_track_rodada")
# `create_type=False`: o tipo é criado uma vez, explicitamente, no upgrade;
# o `sa.Enum` genérico dentro do `create_table` tentava criar de novo.
SITUACAO_COLUNA = postgresql.ENUM(
    "pendente", "avaliada", "justificada", name="situacao_health_track_rodada", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "health_track_rodada",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aberta_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("aberta_por", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("concluida_em", sa.DateTime(), nullable=True),
        sa.Column("concluida_por", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_health_track_rodada_id"), "health_track_rodada", ["id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DO $$ BEGIN CREATE TYPE situacao_health_track_rodada AS ENUM ('pendente', 'avaliada', 'justificada'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )
    else:
        SITUACAO.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "health_track_rodada_projeto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "rodada_id",
            sa.Integer(),
            sa.ForeignKey("health_track_rodada.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("projeto_id", sa.Integer(), sa.ForeignKey("projeto.id", ondelete="CASCADE"), nullable=False),
        sa.Column("situacao", SITUACAO_COLUNA, server_default="pendente", nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=True),
        sa.Column("resolvido_em", sa.DateTime(), nullable=True),
        sa.Column("resolvido_por", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rodada_id", "projeto_id", name="uq_health_track_rodada_projeto"),
    )
    op.create_index(op.f("ix_health_track_rodada_projeto_id"), "health_track_rodada_projeto", ["id"])
    op.create_index("ix_health_track_rodada_projeto_rodada_id", "health_track_rodada_projeto", ["rodada_id"])
    op.create_index("ix_health_track_rodada_projeto_projeto_id", "health_track_rodada_projeto", ["projeto_id"])


def downgrade() -> None:
    op.drop_table("health_track_rodada_projeto")
    op.drop_table("health_track_rodada")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS situacao_health_track_rodada")
