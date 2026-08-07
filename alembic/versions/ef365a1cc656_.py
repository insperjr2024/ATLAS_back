"""renomeia o índice de tarefa.coluna_id para o nome que o modelo espera

O `--autogenerate` gerou só `drop_index` + `create_index`, e o MySQL recusou:

    (1553, "Cannot drop index 'ix_tarefa_coluna_id_fk': needed in a foreign
     key constraint")

⚠ **No MySQL, uma FK precisa de um índice por baixo.** Dropar o índice que a
sustenta é proibido enquanto a FK existir, então renomear exige quatro passos:
soltar a FK, trocar o índice, e recriar a FK por cima do índice novo. É a
mesma correção manual que `1dcac039656c` já teve de fazer neste mesmo par —
o autogenerate não aprende, e vai propor o atalho de novo na próxima vez.

**Por que os nomes divergiam.** O SQLAlchemy deriva o nome implícito do índice
de `ix_` + tabela + coluna, e isso colide para duas colunas diferentes:
`tarefa_coluna.id` e `tarefa.coluna_id` geram ambos `ix_tarefa_coluna_id`.
Migrations antigas desambiguaram à mão com sufixos (`_fk`, `_pk_id`), e desde
então o `alembic check` acusava um desvio permanente entre modelo e schema —
o tipo de ruído que faz ninguém mais olhar para o `check`.

Revision ID: ef365a1cc656
Revises: d3a7b91c5e04
Create Date: 2026-08-07 04:32:12.925409
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "ef365a1cc656"
down_revision: Union[str, Sequence[str], None] = "d3a7b91c5e04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK = "fk_tarefa_coluna"
ANTIGO = "ix_tarefa_coluna_id_fk"
NOVO = "ix_tarefa_coluna_id"


def _indices() -> set:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("tarefa")}


def _tem_fk() -> bool:
    return FK in {f["name"] for f in sa.inspect(op.get_bind()).get_foreign_keys("tarefa")}


def _renomear(de: str, para: str) -> None:
    """Solta a FK, troca o índice, recria a FK. Condicional em cada passo
    porque bancos diferentes chegaram aqui por caminhos diferentes — alguns já
    têm o nome novo, e repetir o DDL quebraria a migration neles."""
    indices = _indices()
    if de not in indices or para in indices:
        return

    tinha_fk = _tem_fk()
    if tinha_fk:
        op.drop_constraint(FK, "tarefa", type_="foreignkey")
    op.drop_index(de, table_name="tarefa")
    op.create_index(para, "tarefa", ["coluna_id"], unique=False)
    if tinha_fk:
        op.create_foreign_key(FK, "tarefa", "tarefa_coluna", ["coluna_id"], ["id"])


def upgrade() -> None:
    _renomear(ANTIGO, NOVO)


def downgrade() -> None:
    _renomear(NOVO, ANTIGO)
