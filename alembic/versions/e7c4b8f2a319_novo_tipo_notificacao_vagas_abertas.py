"""novo_tipo_notificacao_vagas_abertas

Revision ID: e7c4b8f2a319
Revises: d3f8a2c6e951
Create Date: 2026-09-22 23:45:00.000000

⭐ 2026-09-22 — mesmo buraco de `ec14f217db7d`/`e4b1d7c9a052`: valor novo no
enum Python (`vagas_abertas`) precisa existir no Postgres também, ou todo
INSERT desse tipo falha calado (`registrar()` engole a exceção de
propósito).

`ALTER TYPE ... ADD VALUE` não roda dentro do bloco transacional que o
Alembic abre, daí o `autocommit_block`.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7c4b8f2a319'
down_revision: Union[str, Sequence[str], None] = 'd3f8a2c6e951'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS 'vagas_abertas'")


def downgrade() -> None:
    """Sem volta — Postgres não remove valor de enum sem recriar o tipo
    inteiro. Um valor a mais é inofensivo pra quem não o usa."""
    pass
