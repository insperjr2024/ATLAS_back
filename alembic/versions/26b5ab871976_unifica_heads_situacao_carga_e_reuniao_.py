"""Unifica heads situacao carga e reuniao por escopo

Revision ID: 26b5ab871976
Revises: 4fdf0a86da7e, a1c7e4b93d20
Create Date: 2026-08-06 14:45:58.736313

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '26b5ab871976'
down_revision: Union[str, Sequence[str], None] = ('4fdf0a86da7e', 'a1c7e4b93d20')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
