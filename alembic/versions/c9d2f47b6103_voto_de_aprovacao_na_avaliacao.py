"""voto de aprovação na avaliação, e a sessão a que ele pertence

⭐ O resultado da banca passa a ser DERIVADO da maioria dos votos, em vez de
digitado por uma pessoa (ver `utils/apuracao_banca.py`).

Duas colunas, e a segunda é a menos óbvia: `sessao` existe porque
`avaliacao.banca_id` não distingue TENTATIVA. Um escopo com 2ª banca reusa a
mesma linha de `banca`, então sem o discriminador os votos da 1ª contariam na
apuração da 2ª — justamente a sessão que existe para dar uma chance nova.

Ambas com default: toda avaliação existente é da sessão 1 e não tem voto. Zero
data migration.

Revision ID: c9d2f47b6103
Revises: b7e4c91a25f8
Create Date: 2026-08-12 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d2f47b6103"
down_revision: Union[str, Sequence[str], None] = "b7e4c91a25f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("avaliacao", sa.Column("voto_aprovacao", sa.Boolean(), nullable=True))
    op.add_column(
        "avaliacao",
        sa.Column("sessao", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("avaliacao", "sessao")
    op.drop_column("avaliacao", "voto_aprovacao")
