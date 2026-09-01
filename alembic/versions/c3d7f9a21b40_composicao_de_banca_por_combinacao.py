"""composicao de banca por combinacao de frentes

Revision ID: c3d7f9a21b40
Revises: e5c1a9f37b64
Create Date: 2026-09-01

A composição exigida de uma banca passa a depender da COMBINAÇÃO de frentes
que ela avalia, e não mais de um número por frente válido em toda banca.

Antes os números viviam em dois lugares: `frente.piso_banca` (Business 3, Tech
2, Processos 2, Direito 1 — o mesmo em qualquer banca) e
`configuracao.lideranca_minima_por_frente` (um global, hoje 1). Uma banca de
Business sozinha e uma de Business + Tech + Processos exigiam os mesmos 3 de
Business, e não havia teto por frente nenhum: uma banca podia fechar com 5 de
Business e o mínimo de todas as outras.

⚠ **Nada é migrado para cá.** A tabela nasce VAZIA de propósito: combinação sem
linha vale o padrão derivado de `frente.piso_banca`, que é exatamente o
comportamento de hoje. Assim a virada não muda nenhuma banca marcada, e a
diretoria configura as combinações que quiser, quando quiser — e uma frente
cadastrada amanhã já tem regra em todas as combinações sem migration nova.

As duas colunas antigas ficam onde estão: `frente.piso_banca` continua sendo a
fonte do padrão, e `lideranca_minima_por_frente` idem. Removê-las seria uma
segunda mudança, e esta já é grande.
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d7f9a21b40"
down_revision = "e5c1a9f37b64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "banca_composicao_regra",
        sa.Column("id", sa.Integer(), nullable=False),
        # A lista ordenada de ids de frente, unida por "-". Ver
        # `utils/combinacao_frentes.py` — nada monta essa chave à mão.
        sa.Column("combinacao", sa.String(length=120), nullable=False),
        sa.Column("frente_id", sa.Integer(), nullable=False),
        sa.Column("min_membros", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_membros", sa.Integer(), nullable=False, server_default="99"),
        sa.Column("min_lideranca", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_lideranca", sa.Integer(), nullable=False, server_default="99"),
        sa.ForeignKeyConstraint(["frente_id"], ["frente.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "combinacao", "frente_id", name="uq_banca_composicao_combinacao_frente"
        ),
    )
    op.create_index(
        "ix_banca_composicao_regra_combinacao",
        "banca_composicao_regra",
        ["combinacao"],
    )
    op.create_index(
        op.f("ix_banca_composicao_regra_id"), "banca_composicao_regra", ["id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_banca_composicao_regra_id"), table_name="banca_composicao_regra")
    op.drop_index("ix_banca_composicao_regra_combinacao", table_name="banca_composicao_regra")
    op.drop_table("banca_composicao_regra")
