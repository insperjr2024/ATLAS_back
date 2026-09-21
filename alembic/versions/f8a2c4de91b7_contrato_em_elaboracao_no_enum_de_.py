"""contrato_em_elaboracao_no_enum_de_historico

Revision ID: f8a2c4de91b7
Revises: 743e671bffea
Create Date: 2026-09-21 20:30:00.000000

⚠ **O mesmo buraco de `ec14f217db7d`/`e4b1d7c9a052`, dessa vez no enum de
histórico.** `status_projeto` (o enum do `ProjetoModel.status`) ganhou
"contrato_em_elaboracao" quando o projeto passou a nascer nesse status
(§ Contratos, 2026-09-16), mas `status_historico_projeto` — o enum
SEPARADO usado por `ProjetoStatusHistoricoModel.status_novo` — nunca foi
atualizado junto. Toda criação de projeto desde então (normal ou
institucional) grava `status_novo="contrato_em_elaboracao"` no histórico e
estourava `invalid input value for enum status_historico_projeto`,
derrubando a criação inteira com 500 (diferente do bug de notificação: aqui
não há `try/except` que engula, então o projeto às vezes commitava e o
histórico nunca chegava a existir).

`ALTER TYPE ... ADD VALUE` não roda dentro do bloco transacional que o
Alembic abre, daí o `autocommit_block`.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f8a2c4de91b7'
down_revision: Union[str, Sequence[str], None] = '743e671bffea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE status_historico_projeto ADD VALUE IF NOT EXISTS 'contrato_em_elaboracao'"
        )


def downgrade() -> None:
    """Sem volta — mesma razão das anteriores: Postgres não remove valor de
    enum sem recriar o tipo inteiro. Um valor a mais é inofensivo pra quem
    não o usa."""
    pass
