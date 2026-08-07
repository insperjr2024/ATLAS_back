"""unifica heads de pdi cronograma e grade horaria

Revision ID: 1091404c813d
Revises: 380be7bc3345, c16324304443
Create Date: 2026-08-07 00:38:16.240601

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1091404c813d'
down_revision: Union[str, Sequence[str], None] = ('380be7bc3345', 'c16324304443')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
