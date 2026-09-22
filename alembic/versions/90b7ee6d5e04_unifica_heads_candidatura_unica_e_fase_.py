"""unifica heads: candidatura unica e fase 1 de contratos

Revision ID: 90b7ee6d5e04
Revises: 343e1f0be526, 97f768157452
Create Date: 2026-09-16 23:17:37.116330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90b7ee6d5e04'
down_revision: Union[str, Sequence[str], None] = ('343e1f0be526', '97f768157452')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
