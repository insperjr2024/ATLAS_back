"""solicitacao_projeto no enum de notificacao, agora tambem no Postgres

Revision ID: a71c4e93b8d2
Revises: f3a8c9d21e07
Create Date: 2026-08-12 18:05:00.000000

⚠ **Conserto de duas migrations que passaram sem fazer nada.**

A `d66e88dfc475` e a `88ba2dd49a07` foram geradas por autogenerate num banco
MySQL e saíram na forma `op.alter_column(..., existing_type=mysql.ENUM(...),
type_=sa.Enum(...))`. Em MySQL isso funciona, porque lá o ENUM é propriedade da
COLUNA e reescrever a coluna reescreve a lista de valores.

Em Postgres o ENUM é um TIPO próprio, criado uma vez e compartilhado. O
`alter_column` só troca o tipo da coluna por outro que já exista — ele não
altera o tipo, e não cria valor nenhum. As duas migrations rodaram sem erro e
sem efeito, e `tipo_notificacao` ficou 19 valores no banco contra 20 no modelo.

O estrago era invisível até alguém gravar uma notificação do tipo que faltava:
o consultor pedia para entrar num projeto, a solicitação era gravada, e a
notificação para o coordenador estourava logo depois — deixando um pedido que
existia no banco e que a tela não mostrava.

⚠ `ALTER TYPE ... ADD VALUE` não roda dentro do bloco transacional que o
Alembic abre, daí o `autocommit_block`.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a71c4e93b8d2"
down_revision: Union[str, Sequence[str], None] = "f3a8c9d21e07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VALOR = "solicitacao_projeto"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # MySQL já recebeu o valor pelas duas migrations anteriores.
        return
    with op.get_context().autocommit_block():
        op.execute(f"ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS '{VALOR}'")


def downgrade() -> None:
    """Sem volta.

    Postgres não remove valor de enum: seria preciso recriar o tipo inteiro e
    reescrever a coluna. Como o valor a mais é inofensivo para quem não o usa,
    não vale carregar esse risco só para poder descer uma revisão.
    """
    pass
