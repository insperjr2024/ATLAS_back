"""novo_tipo_notificacao_revisao_interna

Revision ID: c9d1e3f5a728
Revises: b7e2f4a1c936
Create Date: 2026-09-22 14:30:00.000000

⭐ 2026-09-22 — mesmo buraco de `ec14f217db7d`/`e4b1d7c9a052`: valor novo no
enum Python (`documento_contratual_pronto_para_revisao_interna`) precisa
existir no Postgres também, ou todo INSERT desse tipo falha calado
(`registrar()` engole a exceção de propósito).

`ALTER TYPE ... ADD VALUE` não roda dentro do bloco transacional que o
Alembic abre, daí o `autocommit_block`.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c9d1e3f5a728'
down_revision: Union[str, Sequence[str], None] = 'b7e2f4a1c936'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS "
            "'documento_contratual_pronto_para_revisao_interna'"
        )


def downgrade() -> None:
    """Sem volta — Postgres não remove valor de enum sem recriar o tipo
    inteiro. Um valor a mais é inofensivo pra quem não o usa."""
    pass
