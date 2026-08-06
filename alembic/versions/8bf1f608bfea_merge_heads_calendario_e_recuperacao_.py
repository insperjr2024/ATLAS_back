"""merge heads calendario e recuperacao senha

Revision ID: 8bf1f608bfea
Revises: 1f4ca90bfbbb, cc94ea34498d
Create Date: 2026-08-05 23:56:57.847330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8bf1f608bfea'
down_revision: Union[str, Sequence[str], None] = ('1f4ca90bfbbb', 'cc94ea34498d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
