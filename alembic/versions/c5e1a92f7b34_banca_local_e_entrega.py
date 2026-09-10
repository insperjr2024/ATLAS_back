"""banca: local e anexo da entrega

⭐ 2026-09-10, a pedido:

- `local`: onde a banca vai acontecer. Texto livre. Quem é do PROJETO que a
  banca avalia registra, até 1h antes. Aparece nas informações da banca pra
  qualquer um.
- entrega (`entrega_link` OU `entrega_arquivo_*`): consultores e coordenação
  do projeto anexam o link ou o arquivo da entrega, a qualquer momento —
  pra consultar antes ou depois da banca. Um só (link OU arquivo), mesmo
  padrão do anexo de proposta do projeto (conteúdo no banco, não em disco
  efêmero).

Revision ID: c5e1a92f7b34
Revises: a3f8c1e29b47
Create Date: 2026-09-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5e1a92f7b34"
down_revision: Union[str, None] = "a3f8c1e29b47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("banca", sa.Column("local", sa.Text(), nullable=True))
    op.add_column("banca", sa.Column("entrega_link", sa.Text(), nullable=True))
    op.add_column("banca", sa.Column("entrega_arquivo_nome", sa.String(length=255), nullable=True))
    op.add_column("banca", sa.Column("entrega_arquivo_conteudo", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("banca", "entrega_arquivo_conteudo")
    op.drop_column("banca", "entrega_arquivo_nome")
    op.drop_column("banca", "entrega_link")
    op.drop_column("banca", "local")
