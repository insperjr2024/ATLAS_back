"""unifica_heads_antes_do_cronograma

Revision ID: f20cbf22f5ee
Revises: 97c0c770e8ae, f4a2c8e01b93
Create Date: 2026-08-06 20:42:38.303826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f20cbf22f5ee'
down_revision: Union[str, Sequence[str], None] = ('97c0c770e8ae', 'f4a2c8e01b93')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
