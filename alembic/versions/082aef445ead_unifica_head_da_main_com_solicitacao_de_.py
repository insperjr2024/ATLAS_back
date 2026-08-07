"""unifica head da main com solicitacao de projeto

Revision ID: 082aef445ead
Revises: 01f8f776e083, 88ba2dd49a07
Create Date: 2026-08-07 05:36:51.409271

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '082aef445ead'
down_revision: Union[str, Sequence[str], None] = ('01f8f776e083', '88ba2dd49a07')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
