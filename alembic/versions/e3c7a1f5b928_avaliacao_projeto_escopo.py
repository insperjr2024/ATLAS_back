"""Avaliação do Escopo: uma resposta por escopo

Revision ID: e3c7a1f5b928
Revises: d7e2b9a4c610
Create Date: 2026-10-05

A pedido: quem está num projeto com dois escopos da própria frente em
andamento responde a Avaliação do Escopo duas vezes, uma por escopo. Pra
isso a avaliação precisa dizer QUAL escopo avaliou (`projeto_escopo_id`,
nulo na avaliação entre pessoas e nas respostas antigas).

A UNIQUE (lote, avaliador, avaliado) de antes impedia a segunda resposta;
vira um índice único com `coalesce(projeto_escopo_id, 0)` no fim, porque no
Postgres NULL != NULL num UNIQUE e a avaliação entre pessoas perderia a
trava de duplicidade.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3c7a1f5b928"
down_revision: Union[str, Sequence[str], None] = "d7e2b9a4c610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "desempenho_avaliacao",
        sa.Column(
            "projeto_escopo_id",
            sa.Integer(),
            sa.ForeignKey("projeto_escopo.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_desempenho_avaliacao_projeto_escopo_id",
        "desempenho_avaliacao",
        ["projeto_escopo_id"],
    )
    op.drop_constraint("uq_desempenho_avaliacao_par", "desempenho_avaliacao", type_="unique")
    op.create_index(
        "uq_desempenho_avaliacao_par",
        "desempenho_avaliacao",
        ["lote_id", "avaliador_id", "avaliado_id", sa.text("coalesce(projeto_escopo_id, 0)")],
        unique=True,
    )


def downgrade() -> None:
    """Só dá pra voltar se não houver duas respostas da mesma pessoa no mesmo
    lote (o caso que esta migration passou a permitir)."""
    op.drop_index("uq_desempenho_avaliacao_par", table_name="desempenho_avaliacao")
    op.create_unique_constraint(
        "uq_desempenho_avaliacao_par", "desempenho_avaliacao", ["lote_id", "avaliador_id", "avaliado_id"]
    )
    op.drop_index("ix_desempenho_avaliacao_projeto_escopo_id", table_name="desempenho_avaliacao")
    op.drop_column("desempenho_avaliacao", "projeto_escopo_id")
