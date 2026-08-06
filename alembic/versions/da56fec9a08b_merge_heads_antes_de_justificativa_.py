"""merge heads antes de justificativa atraso

Revision ID: da56fec9a08b
Revises: 21adfe0d3a5c, 26b5ab871976
Create Date: 2026-08-06 16:57:06.288196

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da56fec9a08b'
down_revision: Union[str, Sequence[str], None] = ('21adfe0d3a5c', '26b5ab871976')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
