"""banca_sessao.cancelada_em: a tentativa cancelada fica no histórico

Revision ID: d5a8b2c7e391
Revises: c4f7a1e9b285
Create Date: 2026-10-13

Marcar de novo uma banca cancelada vira uma tentativa nova: a cancelada é
arquivada em `banca_sessao` com esta coluna, e `banca.cancelada_em` é
limpo. Antes a remarcação só trocava a data e a banca seguia "cancelada".
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5a8b2c7e391"
down_revision: Union[str, Sequence[str], None] = "c4f7a1e9b285"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("banca_sessao", sa.Column("cancelada_em", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("banca_sessao", "cancelada_em")
