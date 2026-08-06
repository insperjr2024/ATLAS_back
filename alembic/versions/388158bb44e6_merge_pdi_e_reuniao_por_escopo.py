"""merge_pdi_e_reuniao_por_escopo

Revision ID: 388158bb44e6
Revises: 5c96b67076b0, a1c7e4b93d20
Create Date: 2026-08-06 14:08:56.643994

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '388158bb44e6'
down_revision: Union[str, Sequence[str], None] = ('5c96b67076b0', 'a1c7e4b93d20')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
