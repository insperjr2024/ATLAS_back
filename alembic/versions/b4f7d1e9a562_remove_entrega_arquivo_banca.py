"""remove_entrega_arquivo_banca

Revision ID: b4f7d1e9a562
Revises: c2a9d5e8b731
Create Date: 2026-09-22 23:00:00.000000

⭐ 2026-09-22 — a pedido: a entrega da banca era link OU arquivo (upload).
Tira o arquivo, fica só link. Nenhuma banca no sandbox tinha arquivo
anexado — sem dado real pra perder.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b4f7d1e9a562'
down_revision: Union[str, Sequence[str], None] = 'c2a9d5e8b731'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("banca", "entrega_arquivo_nome")
    op.drop_column("banca", "entrega_arquivo_conteudo")


def downgrade() -> None:
    op.add_column("banca", sa.Column("entrega_arquivo_nome", sa.String(255), nullable=True))
    op.add_column("banca", sa.Column("entrega_arquivo_conteudo", sa.LargeBinary(), nullable=True))
