"""merge heads apos pull de main (reajuste cronograma, senha provisoria, justificativa atraso)

Revision ID: 9e8caba578b6
Revises: 97c0c770e8ae, 9a51233fa680, f4a2c8e01b93
Create Date: 2026-08-06 18:52:03.115354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e8caba578b6'
down_revision: Union[str, Sequence[str], None] = ('97c0c770e8ae', '9a51233fa680', 'f4a2c8e01b93')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
