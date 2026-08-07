"""unindo todas as heads

Revision ID: 01f8f776e083
Revises: 03ea41a273d0, ef365a1cc656
Create Date: 2026-08-07 05:10:16.001142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '01f8f776e083'
down_revision: Union[str, Sequence[str], None] = ('03ea41a273d0', 'ef365a1cc656')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
