"""merge heads apos reversao do reajuste de cronograma

Revision ID: 3ae5c0c244c0
Revises: 1556cc590a06, 9e8caba578b6
Create Date: 2026-08-06 20:07:27.525444

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ae5c0c244c0'
down_revision: Union[str, Sequence[str], None] = ('1556cc590a06', '9e8caba578b6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
