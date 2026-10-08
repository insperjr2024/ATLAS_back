"""health track: ações

Revision ID: c8e4a6b2f095
Revises: b6c2e4a8d173
Create Date: 2026-10-08

Ver `models/health_track_acao_model.py` (§15): problema, responsável,
próxima ação e prazo por projeto.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8e4a6b2f095"
down_revision: Union[str, Sequence[str], None] = "b6c2e4a8d173"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "health_track_acao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("projeto_id", sa.Integer(), sa.ForeignKey("projeto.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pilar_id", sa.Integer(), sa.ForeignKey("health_track_pilar.id"), nullable=True),
        sa.Column("problema", sa.Text(), nullable=False),
        sa.Column("proxima_acao", sa.Text(), nullable=False),
        sa.Column("responsavel_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("prazo", sa.Date(), nullable=True),
        sa.Column("concluida_em", sa.DateTime(), nullable=True),
        sa.Column("concluida_por", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("criado_por", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_health_track_acao_id"), "health_track_acao", ["id"])
    op.create_index("ix_health_track_acao_projeto_id", "health_track_acao", ["projeto_id"])


def downgrade() -> None:
    op.drop_table("health_track_acao")
