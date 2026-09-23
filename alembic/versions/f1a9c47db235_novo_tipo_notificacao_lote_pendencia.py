"""novo_tipo_notificacao_lote_pendencia

Revision ID: f1a9c47db235
Revises: c1b1fbcf9f4d
Create Date: 2026-09-23 12:00:00.000000

⭐ 2026-09-23 — mesmo buraco de `ec14f217db7d`/`e4b1d7c9a052`: valor novo no
enum Python (`lote_desempenho_pendencia_diretoria`) precisa existir no
Postgres também, ou todo INSERT desse tipo falha calado (`registrar()`
engole a exceção de propósito).

`ALTER TYPE ... ADD VALUE` não roda dentro do bloco transacional que o
Alembic abre, daí o `autocommit_block`.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1a9c47db235'
down_revision: Union[str, Sequence[str], None] = 'c1b1fbcf9f4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS 'lote_desempenho_pendencia_diretoria'")


def downgrade() -> None:
    """Sem volta — Postgres não remove valor de enum sem recriar o tipo
    inteiro. Um valor a mais é inofensivo pra quem não o usa."""
    pass
