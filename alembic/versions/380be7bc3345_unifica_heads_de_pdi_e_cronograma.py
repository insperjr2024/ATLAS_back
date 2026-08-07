"""Unifica heads de pdi e cronograma

Revision ID: 380be7bc3345
Revises: 97c0c770e8ae, f4a2c8e01b93
Create Date: 2026-08-06 18:14:51.231532

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '380be7bc3345'
down_revision: Union[str, Sequence[str], None] = ('97c0c770e8ae', 'f4a2c8e01b93')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
