"""composicao de banca sem teto por frente

Revision ID: 4f878bd409aa
Revises: 74f50831795e
Create Date: 2026-09-03

O piso por frente continua (X membros + Y lideranca DAQUELA frente), mas o
TETO por frente saiu (2026-09-03, a pedido da diretoria): completar a banca
acima do piso e "tanto faz a frente", o unico teto e o total da banca
(`vagas`).

Dropa `max_membros` e `max_lideranca` de `banca_composicao_regra`. Nada a
migrar: os valores eram limites que deixaram de valer.
"""

import sqlalchemy as sa
from alembic import op

revision = "4f878bd409aa"
down_revision = "74f50831795e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("banca_composicao_regra", "max_membros")
    op.drop_column("banca_composicao_regra", "max_lideranca")


def downgrade() -> None:
    op.add_column(
        "banca_composicao_regra",
        sa.Column(
            "max_lideranca",
            sa.Integer(),
            nullable=False,
            server_default="99",
        ),
    )
    op.add_column(
        "banca_composicao_regra",
        sa.Column(
            "max_membros",
            sa.Integer(),
            nullable=False,
            server_default="99",
        ),
    )
