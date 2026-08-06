"""concilia calendario por frente com a main

Revision ID: cc94ea34498d
Revises: 4930cc1e271e, e477c6def091
Create Date: 2026-08-05 23:33:34.401569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc94ea34498d'
down_revision: Union[str, Sequence[str], None] = ('4930cc1e271e', 'e477c6def091')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
