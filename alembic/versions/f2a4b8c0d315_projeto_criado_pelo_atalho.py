"""projeto.criado_pelo_atalho

Revision ID: f2a4b8c0d315
Revises: e1f3a7c9d204
Create Date: 2026-10-14

Projeto nascido pelo atalho não é cobrado de kickoff (sem pendência, sem
alerta, sem travar status, cronograma e banca) e não abre a declaração de
interesse sozinho. Os que já existem nascem com a coluna em falso.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a4b8c0d315"
down_revision: Union[str, Sequence[str], None] = "e1f3a7c9d204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projeto",
        sa.Column("criado_pelo_atalho", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("projeto", "criado_pelo_atalho")
