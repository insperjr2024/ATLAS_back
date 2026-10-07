"""avaliacao.comentario_feedback sem limite de tamanho

Revision ID: e5a1c7d9b304
Revises: c8d2f4a6e917
Create Date: 2026-10-06

Era `varchar(1000)`. Um comentário de banca mais longo que isso derrubava
o "submeter" com 500 (StringDataRightTruncation), e a pessoa ficava com o
rascunho salvo sem conseguir enviar. Vira `text`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5a1c7d9b304"
down_revision: Union[str, Sequence[str], None] = "c8d2f4a6e917"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "avaliacao",
        "comentario_feedback",
        existing_type=sa.String(length=1000),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Volta pro limite antigo; falha se já houver comentário maior que 1000."""
    op.alter_column(
        "avaliacao",
        "comentario_feedback",
        existing_type=sa.Text(),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )
