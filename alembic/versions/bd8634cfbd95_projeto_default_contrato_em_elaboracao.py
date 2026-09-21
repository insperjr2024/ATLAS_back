"""projeto_default_contrato_em_elaboracao

Revision ID: bd8634cfbd95
Revises: db182fa99145
Create Date: 2026-09-21 17:34:14.988954

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd8634cfbd95'
down_revision: Union[str, Sequence[str], None] = 'db182fa99145'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("projeto", "status", server_default="contrato_em_elaboracao")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("projeto", "status", server_default="vendido")
