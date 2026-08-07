"""unifica head do limpar-historico com o head da main

Revision ID: ae652f7be7a2
Revises: f4a2c8e01b93, f81c58ed626c
Create Date: 2026-08-06 20:44:36.166096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae652f7be7a2'
down_revision: Union[str, Sequence[str], None] = ('f4a2c8e01b93', 'f81c58ed626c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
