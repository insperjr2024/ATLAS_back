"""desempenho_lote.banca_id

⭐ 2026-09-05, a pedido: cancelar uma banca DEPOIS de realizada (imprevisto,
deu problema em cima da hora) precisa desfazer o lote de desempenho de
finalização que a automação abriu sozinha — e sem saber QUAL banca abriu
QUAL lote, não dá pra fazer isso com segurança (poderia fechar o lote
errado). `banca_id` é essa referência: nula pra todo lote que nunca veio de
uma banca (periódica, ou finalização aberta à mão), preenchida só pelo
`FinalizacaoAutomaticaBancaUseCase`.

`ondelete=SET NULL`: apagar a banca não pode quebrar o lote — o lote de
desempenho continua valendo por si (as avaliações já respondidas não
dependem da banca existir), só perde a referência de onde veio.

Revision ID: d4e9a7c2f156
Revises: c1a2f4e8b3d7
Create Date: 2026-09-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e9a7c2f156"
down_revision: Union[str, None] = "c1a2f4e8b3d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "desempenho_lote",
        sa.Column("banca_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_desempenho_lote_banca_id",
        "desempenho_lote",
        "banca",
        ["banca_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_desempenho_lote_banca_id", "desempenho_lote", type_="foreignkey")
    op.drop_column("desempenho_lote", "banca_id")
