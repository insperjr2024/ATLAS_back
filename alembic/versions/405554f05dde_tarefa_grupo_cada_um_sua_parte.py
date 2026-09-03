"""tarefa: grupo para "cada um faz a sua parte"

Revision ID: 405554f05dde
Revises: 9e7ed0af2ed6
Create Date: 2026-09-02

Uma tarefa atribuida a varias pessoas pode ser CONJUNTA (um card, um status) ou
"cada um faz a sua parte". Nesse segundo caso o cadastro cria uma tarefa por
pessoa, todas com o mesmo `grupo_id`, e cada card anda no kanban por conta
propria.

`grupo_id` e so um token: as tarefas do grupo tem o mesmo valor. Nulo = tarefa
comum. Nada e migrado; as tarefas existentes ficam com grupo_id nulo.
"""

import sqlalchemy as sa
from alembic import op

revision = "405554f05dde"
down_revision = "9e7ed0af2ed6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tarefa", sa.Column("grupo_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_tarefa_grupo_id"), "tarefa", ["grupo_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tarefa_grupo_id"), table_name="tarefa")
    op.drop_column("tarefa", "grupo_id")
