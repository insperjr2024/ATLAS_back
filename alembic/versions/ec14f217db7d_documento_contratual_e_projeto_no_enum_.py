"""documento_contratual_e_projeto_no_enum_de_notificacao

Revision ID: ec14f217db7d
Revises: 435f93ef5668
Create Date: 2026-09-21 19:47:43.080522

⚠ **O mesmo buraco que `e4b1d7c9a052` fechou, pra sete valores de uma vez.**

`notificar_documento_contratual.py` (Fase 2) e `notificar_projeto.py`
(2026-09-21) emitem estes sete tipos desde que foram escritos, mas nenhum
deles nunca foi declarado no enum do Postgres (nem no do model, corrigido
junto nesta mesma leva). Toda chamada a `registrar()` com um desses tipos
vinha falhando no INSERT (`invalid input value for enum tipo_notificacao`) e
`registrar()` engole a exceção de propósito (§6.6: notificar nunca derruba a
ação que a gerou) — o efeito colateral é que NENHUMA notificação de Contratos
jamais chegou a existir de fato, calado, sem log visível em lugar nenhum que
alguém fosse checar.

`ALTER TYPE ... ADD VALUE` não roda dentro do bloco transacional que o
Alembic abre, daí o `autocommit_block`.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ec14f217db7d'
down_revision: Union[str, Sequence[str], None] = '435f93ef5668'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALORES = (
    "documento_contratual_pronto_para_gerar",
    "documento_contratual_aprovado_internamente",
    "documento_contratual_liberado",
    "documento_contratual_cliente_aprovou",
    "documento_contratual_cliente_pediu_alteracao",
    "projeto_criado_em_contrato",
    "projeto_vendido",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        for valor in VALORES:
            op.execute(f"ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS '{valor}'")


def downgrade() -> None:
    """Sem volta — mesma razão da `e4b1d7c9a052`: Postgres não remove valor
    de enum sem recriar o tipo inteiro. Um valor a mais é inofensivo pra
    quem não o usa."""
    pass
