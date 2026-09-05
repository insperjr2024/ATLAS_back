"""lote_desempenho_lembrete e lote_desempenho_cancelado no enum de notificacao

Revision ID: a2c8f61de930
Revises: d4e9a7c2f156
Create Date: 2026-09-05

⚠ **O mesmo buraco que `e4b1d7c9a052` fechou, de novo — achado nesta
revisão.** `lote_desempenho_lembrete` foi acrescentado ao `Enum(...)` do
model em `notificacao_model.py` (2026-09-04, o lembrete de 24h do lote de
finalização) e usado em `notificar_lote_desempenho_lembrete`, mas nunca
ganhou a migration que o registra no TIPO do Postgres — só o `Enum` do
SQLAlchemy foi atualizado, o que não basta neste banco (ver o docstring de
`e4b1d7c9a052` para o porquê). Sem isto, `rodar_lembrete_lote_finalizacao`
quebraria na primeira pessoa que ainda não tivesse terminado 24h depois de
um lote de finalização abrir — nunca chegou a rodar em produção a tempo de
doer, mas ia doer.

De caminho, `lote_desempenho_cancelado` entra junto — o aviso de
`CancelarBancaUseCase` quando alguém cancela uma banca DEPOIS dela já ter
sido marcada realizada, desfazendo o lote de desempenho que a automação
tinha aberto sozinha.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a2c8f61de930"
down_revision: Union[str, Sequence[str], None] = "d4e9a7c2f156"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VALORES = ["lote_desempenho_lembrete", "lote_desempenho_cancelado"]


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        for valor in VALORES:
            op.execute(f"ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS '{valor}'")


def downgrade() -> None:
    """Sem volta — mesma razão da `e4b1d7c9a052`: Postgres não remove valor
    de enum sem recriar o tipo inteiro. Inofensivo para quem não usa."""
    pass
