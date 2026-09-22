"""projeto_vagas_abertas

Revision ID: d3f8a2c6e951
Revises: b4f7d1e9a562
Create Date: 2026-09-22 23:30:00.000000

⭐ 2026-09-22 — a pedido: interruptor explícito de declaração de interesse
em Vagas em Projetos, substitui o cálculo puro de `max_consultores -
alocados` como critério de "tem vaga". O `server_default` já fecha todo
projeto existente (nenhum backfill extra necessário) — só quem assinar o
Contrato de PS a partir de agora, ou quem abrir manualmente, abre vagas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3f8a2c6e951'
down_revision: Union[str, Sequence[str], None] = 'b4f7d1e9a562'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projeto",
        sa.Column("vagas_abertas", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("projeto", "vagas_abertas")
