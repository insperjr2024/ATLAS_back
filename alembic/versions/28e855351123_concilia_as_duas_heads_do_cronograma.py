"""concilia as duas heads do cronograma

Revision ID: 28e855351123
Revises: 88728a91f918, fb72df6402d6
Create Date: 2026-08-05 11:21:24.289754

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28e855351123'
down_revision: Union[str, Sequence[str], None] = ('88728a91f918', 'fb72df6402d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
