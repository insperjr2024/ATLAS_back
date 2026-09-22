"""projeto_institucional

Revision ID: 743e671bffea
Revises: ec14f217db7d
Create Date: 2026-09-21 20:23:54.387248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '743e671bffea'
down_revision: Union[str, Sequence[str], None] = 'ec14f217db7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "projeto",
        sa.Column("institucional", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("projeto", "institucional")
