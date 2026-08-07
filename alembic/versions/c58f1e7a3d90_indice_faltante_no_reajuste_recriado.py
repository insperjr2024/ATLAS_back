"""indice_faltante_no_reajuste_recriado

Conserta um esquecimento de `b1c4d7e90a22`.

Aquela migration recriou `cronograma_reajuste_solicitacao`, que a reversão da
main havia dropado, copiando a definição da migration original — mas a original
criava só o índice de `id`, e o modelo declara `index=True` também em
`projeto_escopo_id`. O índice daquela coluna existia no banco antigo porque a
FK do MySQL o cria por baixo dos panos com outro nome; ao recriar a tabela do
zero, o nome que o SQLAlchemy espera não apareceu, e o `alembic check` passou a
acusar desvio entre modelo e schema.

Sem ele nada quebra — a consulta por escopo continua usando o índice implícito
da FK. O que quebra é a confiança no `alembic check`: com um desvio conhecido
sempre presente, ninguém percebe o próximo.

Revision ID: c58f1e7a3d90
Revises: 339b2ac7eb3b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c58f1e7a3d90"
down_revision: Union[str, Sequence[str], None] = "339b2ac7eb3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDICE = "ix_cronograma_reajuste_solicitacao_projeto_escopo_id"
TABELA = "cronograma_reajuste_solicitacao"


def _tem_indice() -> bool:
    inspetor = sa.inspect(op.get_bind())
    if TABELA not in inspetor.get_table_names():
        return False
    return INDICE in {i["name"] for i in inspetor.get_indexes(TABELA)}


def upgrade() -> None:
    # Condicional porque bancos que nunca passaram pela reversão da main
    # mantiveram a tabela original — e nela o índice pode já existir.
    if not _tem_indice():
        op.create_index(INDICE, TABELA, ["projeto_escopo_id"], unique=False)


def downgrade() -> None:
    if _tem_indice():
        op.drop_index(INDICE, table_name=TABELA)
