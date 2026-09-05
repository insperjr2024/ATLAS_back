"""banca cancelada

`banca.cancelada_em` — a saída pra "isto não vai acontecer" agora que
`data_hora` passar sozinho dispara a realização automática (ver
`use_cases/banca/finalizacao_automatica.py`) e as avaliações que vêm dela.
Cancelar antes de `realizado_em` tira a banca desse trilho: o job de
finalização automática pula quem tem `cancelada_em` preenchido.

Revision ID: c1a2f4e8b3d7
Revises: 8b9d69103957
Create Date: 2026-09-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a2f4e8b3d7"
down_revision: Union[str, Sequence[str], None] = "8b9d69103957"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("banca", sa.Column("cancelada_em", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("banca", "cancelada_em")
