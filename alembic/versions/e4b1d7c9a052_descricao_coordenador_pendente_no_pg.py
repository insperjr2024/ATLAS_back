"""descricao_coordenador_pendente no enum de notificacao, tambem no Postgres

Revision ID: e4b1d7c9a052
Revises: 925c8d1287b1
Create Date: 2026-08-13 12:05:00.000000

⚠ **O mesmo buraco que `a71c4e93b8d2` fechou, para outro valor.**

`descricao_coordenador_pendente` foi acrescentado à mão na `d66e88dfc475`, numa
chamada `op.alter_column(..., existing_type=mysql.ENUM(...), type_=sa.Enum(...))`.
Em MySQL isso funciona: o ENUM é propriedade da COLUNA, e reescrever a coluna
reescreve a lista de valores.

Em Postgres o ENUM é um TIPO próprio. `alter_column` só troca a coluna por um
tipo que já exista — não cria valor nenhum. A migration passa sem erro e sem
efeito, e o tipo fica com um valor a menos que o model.

O estrago é invisível até alguém registrar a REALIZAÇÃO de uma banca: é ali que
`marcar_banca_escopo.py` emite a notificação `descricao_coordenador_pendente`
para o coordenador. Em Postgres a banca seria marcada como realizada e a
notificação estouraria logo depois — o mesmo sintoma que a `a71c4e93b8d2`
descreve para `solicitacao_projeto`.

⚠ `ALTER TYPE ... ADD VALUE` não roda dentro do bloco transacional que o Alembic
abre, daí o `autocommit_block`.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4b1d7c9a052"
down_revision: Union[str, Sequence[str], None] = "925c8d1287b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VALOR = "descricao_coordenador_pendente"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # MySQL já recebeu o valor pela `d66e88dfc475`.
        return
    with op.get_context().autocommit_block():
        op.execute(f"ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS '{VALOR}'")


def downgrade() -> None:
    """Sem volta — mesma razão da `a71c4e93b8d2`.

    Postgres não remove valor de enum sem recriar o tipo inteiro e reescrever a
    coluna. Um valor a mais é inofensivo para quem não o usa.
    """
    pass
