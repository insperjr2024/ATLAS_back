"""cliente_opcional_no_projeto

Revision ID: 3a55df5fef52
Revises: c16324304443
Create Date: 2026-08-06 23:51:53.001367

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a55df5fef52'
down_revision: Union[str, Sequence[str], None] = 'c16324304443'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "projeto", "cliente", existing_type=sa.String(length=150), nullable=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    # ⚠ Projetos criados sem cliente (agora permitido) ficariam com NULL numa
    # coluna NOT NULL — MySQL aceitaria trocando o vazio por '', mas o
    # Postgres recusa o ALTER com linha nula na coluna. Backfill primeiro.
    op.execute("UPDATE projeto SET cliente = '' WHERE cliente IS NULL")
    op.alter_column(
        "projeto", "cliente", existing_type=sa.String(length=150), nullable=False
    )
