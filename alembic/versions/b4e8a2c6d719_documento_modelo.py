"""documento_modelo: modelo base (.docx) por tipo, trocável pela diretoria

Revision ID: b4e8a2c6d719
Revises: a7c3e9b5d218
Create Date: 2026-10-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4e8a2c6d719"
down_revision: Union[str, Sequence[str], None] = "a7c3e9b5d218"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documento_modelo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("arquivo_nome", sa.String(length=255), nullable=False),
        sa.Column("arquivo_conteudo", sa.LargeBinary(), nullable=False),
        sa.Column("enviado_por", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("enviado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tipo"),
    )
    op.create_index(op.f("ix_documento_modelo_id"), "documento_modelo", ["id"])


def downgrade() -> None:
    op.drop_table("documento_modelo")
