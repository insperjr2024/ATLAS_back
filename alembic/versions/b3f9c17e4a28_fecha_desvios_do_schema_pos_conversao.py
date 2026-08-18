"""fecha os tres desvios entre o schema do Postgres e os models

O banco de producao veio de uma conversao do MySQL antigo, e sobraram tres
diferencas que o `alembic check` acusa a cada rodada:

1. `ix_cronograma_reajuste_solicitacao_projeto_escopo_id` nao existe. E o
   indice que `c58f1e7a3d90` cria — mas aquela migration e condicional e
   nunca chegou a rodar neste banco, que estava com o `alembic_version`
   apontando para uma revisao inexistente.

2. `tarefa_coluna` tem `ix_tarefa_coluna_pk_id`, e o autogenerate pedia para
   renomear para `ix_tarefa_coluna_id`. A renomeacao e impossivel: esse nome
   ja pertence ao indice de `tarefa.coluna_id`, e nome de indice no Postgres
   e unico por schema, nao por tabela. `tarefa_coluna.id` e `tarefa.coluna_id`
   geram o mesmo nome pela convencao do SQLAlchemy.

   O nome esquisito de `96bc443dfc15` era a fuga da colisao, feita no banco.
   O comentario de `deda213224f9` ja tinha visto o desvio e o classificado
   como ruido. Era um bug latente nos models: dois Index com o mesmo nome no
   mesmo metadata — um `create_all` num banco vazio falharia.

   A correcao foi no model, tirando o `index=True` da PK de `tarefa_coluna`
   (redundante: `tarefa_coluna_pkey` ja cobre a coluna). Aqui so cai o indice
   que sobrou no banco.

3. `solicitacao_projeto.status` e `VARCHAR(20)`, e o model declara o enum
   `status_solicitacao_projeto`. O tipo enum nem existe no banco: o conversor
   rebaixou a coluna para texto.

Nenhum dos tres quebra a aplicacao hoje. O que eles quebram e o
`alembic check` — pelo mesmo motivo que `c58f1e7a3d90` ja registrou: com um
desvio conhecido sempre presente, ninguem percebe o proximo. E foi
exatamente um desvio despercebido que deixou o ponteiro deste banco
apontando para o vazio.

Tudo condicional: num banco construido do zero pela cadeia de migrations os
tres pontos ja estao certos, e ali esta migration nao faz nada.

Revision ID: b3f9c17e4a28
Revises: 14390b63b8c6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b3f9c17e4a28"
down_revision: Union[str, Sequence[str], None] = "14390b63b8c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDICE_REAJUSTE = "ix_cronograma_reajuste_solicitacao_projeto_escopo_id"
TABELA_REAJUSTE = "cronograma_reajuste_solicitacao"

TABELA_COLUNA = "tarefa_coluna"
INDICE_COLUNA_REDUNDANTE = "ix_tarefa_coluna_pk_id"

STATUS_ENUM = sa.Enum(
    "pendente", "aprovada", "recusada", name="status_solicitacao_projeto"
)


def _indices(tabela: str) -> set:
    inspetor = sa.inspect(op.get_bind())
    if tabela not in inspetor.get_table_names():
        return set()
    return {i["name"] for i in inspetor.get_indexes(tabela)}


def _status_ja_e_enum() -> bool:
    udt = (
        op.get_bind()
        .execute(
            sa.text(
                "select udt_name from information_schema.columns "
                "where table_name = 'solicitacao_projeto' and column_name = 'status'"
            )
        )
        .scalar()
    )
    return udt == "status_solicitacao_projeto"


def upgrade() -> None:
    if INDICE_REAJUSTE not in _indices(TABELA_REAJUSTE):
        op.create_index(
            INDICE_REAJUSTE, TABELA_REAJUSTE, ["projeto_escopo_id"], unique=False
        )

    if INDICE_COLUNA_REDUNDANTE in _indices(TABELA_COLUNA):
        op.drop_index(INDICE_COLUNA_REDUNDANTE, table_name=TABELA_COLUNA)

    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and not _status_ja_e_enum():
        # O default cai antes do ALTER TYPE: ele ainda e um literal de varchar,
        # e o Postgres nao converte o default junto com a coluna.
        STATUS_ENUM.create(bind, checkfirst=True)
        op.execute("ALTER TABLE solicitacao_projeto ALTER COLUMN status DROP DEFAULT")
        op.execute(
            "ALTER TABLE solicitacao_projeto ALTER COLUMN status "
            "TYPE status_solicitacao_projeto "
            "USING status::text::status_solicitacao_projeto"
        )
        op.execute(
            "ALTER TABLE solicitacao_projeto ALTER COLUMN status "
            "SET DEFAULT 'pendente'::status_solicitacao_projeto"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and _status_ja_e_enum():
        op.execute("ALTER TABLE solicitacao_projeto ALTER COLUMN status DROP DEFAULT")
        op.execute(
            "ALTER TABLE solicitacao_projeto ALTER COLUMN status "
            "TYPE VARCHAR(20) USING status::text"
        )
        op.execute(
            "ALTER TABLE solicitacao_projeto ALTER COLUMN status SET DEFAULT 'pendente'"
        )
        STATUS_ENUM.drop(bind, checkfirst=True)

    if INDICE_COLUNA_REDUNDANTE not in _indices(TABELA_COLUNA):
        op.create_index(INDICE_COLUNA_REDUNDANTE, TABELA_COLUNA, ["id"], unique=False)

    if INDICE_REAJUSTE in _indices(TABELA_REAJUSTE):
        op.drop_index(INDICE_REAJUSTE, table_name=TABELA_REAJUSTE)
