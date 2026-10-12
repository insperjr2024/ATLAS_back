"""push: inscrições de aparelho

Revision ID: c4f7a1e9b285
Revises: b8e4c2a6d930
Create Date: 2026-10-12

Tabela `push_inscricao`: cada aparelho/navegador em que a pessoa ativou a
notificação push. Ver `models/push_inscricao_model.py`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4f7a1e9b285"
down_revision: Union[str, Sequence[str], None] = "b8e4c2a6d930"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_inscricao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.String(1000), nullable=False),
        sa.Column("p256dh", sa.String(200), nullable=False),
        sa.Column("auth", sa.String(100), nullable=False),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("ultimo_envio_em", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("endpoint", name="uq_push_inscricao_endpoint"),
    )
    op.create_index(op.f("ix_push_inscricao_id"), "push_inscricao", ["id"])
    op.create_index(op.f("ix_push_inscricao_usuario_id"), "push_inscricao", ["usuario_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_push_inscricao_usuario_id"), table_name="push_inscricao")
    op.drop_index(op.f("ix_push_inscricao_id"), table_name="push_inscricao")
    op.drop_table("push_inscricao")
