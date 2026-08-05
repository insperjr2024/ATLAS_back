"""merge heads desempenho e permissoes

Revision ID: 5174eecb3b89
Revises: 16ccf74cebdd, b750178a39d0
Create Date: 2026-08-05 16:25:22.439218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5174eecb3b89'
down_revision: Union[str, Sequence[str], None] = ('16ccf74cebdd', 'b750178a39d0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
