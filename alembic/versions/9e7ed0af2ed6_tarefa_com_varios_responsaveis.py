"""tarefa com varios responsaveis

Revision ID: 9e7ed0af2ed6
Revises: a893953b013c
Create Date: 2026-09-02

Uma tarefa passa a ter N responsaveis (`tarefa_responsavel`) em vez de um
`tarefa.responsavel_id` NOT NULL. Serve para atribuir a varias pessoas ou a
todos os consultores do projeto.

O `responsavel_id` de cada tarefa vira uma linha em `tarefa_responsavel`, e a
coluna e removida.

Sem indice explicito em `tarefa_responsavel.id`: a PK ja e indexada pelo
Postgres, e o nome que o SQLAlchemy daria (`ix_tarefa_responsavel_id`)
colide com o indice da coluna antiga `tarefa.responsavel_id`, que ainda
existe quando esta migration roda.
"""

import sqlalchemy as sa
from alembic import op

revision = "9e7ed0af2ed6"
down_revision = "a893953b013c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tarefa_responsavel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tarefa_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tarefa_id"], ["tarefa.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tarefa_id", "usuario_id", name="uq_tarefa_responsavel"),
    )
    op.create_index(
        op.f("ix_tarefa_responsavel_tarefa_id"), "tarefa_responsavel", ["tarefa_id"]
    )
    op.create_index(
        op.f("ix_tarefa_responsavel_usuario_id"), "tarefa_responsavel", ["usuario_id"]
    )

    op.execute(
        """
        INSERT INTO tarefa_responsavel (tarefa_id, usuario_id)
        SELECT id, responsavel_id FROM tarefa
        """
    )

    op.drop_column("tarefa", "responsavel_id")


def downgrade() -> None:
    op.add_column(
        "tarefa",
        sa.Column("responsavel_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE tarefa
        SET responsavel_id = (
            SELECT tr.usuario_id FROM tarefa_responsavel tr
            WHERE tr.tarefa_id = tarefa.id
            ORDER BY tr.id
            LIMIT 1
        )
        """
    )
    op.alter_column("tarefa", "responsavel_id", nullable=False)

    op.drop_index(op.f("ix_tarefa_responsavel_usuario_id"), table_name="tarefa_responsavel")
    op.drop_index(op.f("ix_tarefa_responsavel_tarefa_id"), table_name="tarefa_responsavel")
    op.drop_table("tarefa_responsavel")
