"""formulário de desempenho: versão congelada por lote aberto

Revision ID: a7c3e9b5d218
Revises: f2b8d4e6a195
Create Date: 2026-10-06

A pedido: editar um formulário com lote aberto pergunta se aplica ao lote
em andamento ou só a futuros. "Só a futuros" exige guardar a versão antiga
pro lote: `vigente`/`congelado_em` no formulário (a UNIQUE (tipo, papel)
vira índice único parcial sobre os vigentes) e a tabela
`desempenho_lote_formulario` dizendo qual versão cada lote usa.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c3e9b5d218"
down_revision: Union[str, Sequence[str], None] = "f2b8d4e6a195"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "desempenho_formulario",
        sa.Column("vigente", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("desempenho_formulario", sa.Column("congelado_em", sa.DateTime(), nullable=True))
    op.drop_constraint("uq_desempenho_formulario_tipo_papel", "desempenho_formulario", type_="unique")
    op.create_index(
        "uq_desempenho_formulario_vigente",
        "desempenho_formulario",
        ["tipo", "papel"],
        unique=True,
        postgresql_where=sa.text("vigente"),
    )
    op.create_table(
        "desempenho_lote_formulario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "lote_id", sa.Integer(), sa.ForeignKey("desempenho_lote.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("papel", sa.String(length=20), nullable=False),
        sa.Column("formulario_id", sa.Integer(), sa.ForeignKey("desempenho_formulario.id"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lote_id", "papel", name="uq_desempenho_lote_formulario"),
    )
    op.create_index(op.f("ix_desempenho_lote_formulario_id"), "desempenho_lote_formulario", ["id"])
    op.create_index("ix_desempenho_lote_formulario_lote_id", "desempenho_lote_formulario", ["lote_id"])
    op.create_index("ix_desempenho_lote_formulario_formulario_id", "desempenho_lote_formulario", ["formulario_id"])


def downgrade() -> None:
    """Só volta se não houver versão congelada (a UNIQUE antiga não aceita)."""
    op.drop_table("desempenho_lote_formulario")
    op.drop_index("uq_desempenho_formulario_vigente", table_name="desempenho_formulario")
    op.create_unique_constraint("uq_desempenho_formulario_tipo_papel", "desempenho_formulario", ["tipo", "papel"])
    op.drop_column("desempenho_formulario", "congelado_em")
    op.drop_column("desempenho_formulario", "vigente")
