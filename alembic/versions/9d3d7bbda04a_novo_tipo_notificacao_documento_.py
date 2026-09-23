"""novo_tipo_notificacao_documento_contratual_assinado

Revision ID: 9d3d7bbda04a
Revises: c095d39e2df6
Create Date: 2026-09-23 00:00:00.000000

⭐ 2026-09-23 — mesmo buraco de `ec14f217db7d`/`e4b1d7c9a052`/`e7c4b8f2a319`:
valor novo no enum Python (`documento_contratual_assinado`) precisa existir
no Postgres também, ou todo INSERT desse tipo falha calado (`registrar()`
engole a exceção de propósito).

`ALTER TYPE ... ADD VALUE` não roda dentro do bloco transacional que o
Alembic abre, daí o `autocommit_block`.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9d3d7bbda04a'
down_revision: Union[str, Sequence[str], None] = 'c095d39e2df6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS 'documento_contratual_assinado'")


def downgrade() -> None:
    """Sem volta — Postgres não remove valor de enum sem recriar o tipo
    inteiro. Um valor a mais é inofensivo pra quem não o usa."""
    pass
