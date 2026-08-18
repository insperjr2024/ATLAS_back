"""planilha no enum de tipo_arquivo do item de PDI

Revision ID: 7f4b0183bfc7
Revises: 14390b63b8c6
Create Date: 2026-08-18 00:00:00.000000

Novo valor do ENUM `desempenho_pdi_item_tipo_arquivo` (Postgres), pra quem
cadastra um item de PDI poder exigir uma planilha (.xlsx/.xls) em vez de só
documento/foto/qualquer — ver `validar_arquivo_pdi.py`.

⚠ `ALTER TYPE ... ADD VALUE` não roda dentro do bloco transacional que o
Alembic abre, daí o `autocommit_block` (mesmo padrão de `a71c4e93b8d2`).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f4b0183bfc7"
down_revision: Union[str, Sequence[str], None] = "14390b63b8c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE desempenho_pdi_item_tipo_arquivo ADD VALUE IF NOT EXISTS 'planilha'"
        )


def downgrade() -> None:
    """Sem volta — mesmo motivo de `a71c4e93b8d2`: Postgres não remove valor
    de enum sem recriar o tipo inteiro, e o valor a mais é inofensivo."""
    pass
