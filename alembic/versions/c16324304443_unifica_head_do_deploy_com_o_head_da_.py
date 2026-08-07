"""unifica head do deploy com o head da grade horaria

Revision ID: c16324304443
Revises: ae652f7be7a2, af99d9ec2483
Create Date: 2026-08-06 23:45:40.111533

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c16324304443'
down_revision: Union[str, Sequence[str], None] = ('ae652f7be7a2', 'af99d9ec2483')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
