"""merge_permissoes_cargo_e_desempenho

Revision ID: d23f2cba6f5d
Revises: 16ccf74cebdd, b750178a39d0
Create Date: 2026-08-05 11:37:13.458860

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd23f2cba6f5d'
down_revision: Union[str, Sequence[str], None] = ('16ccf74cebdd', 'b750178a39d0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
