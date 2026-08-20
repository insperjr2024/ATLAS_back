"""data_inicio_ambientacao_no_projeto

Revision ID: 7cd394623af4
Revises: c7d2a04f8b16
Create Date: 2026-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cd394623af4'
down_revision: Union[str, Sequence[str], None] = 'c7d2a04f8b16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projeto', sa.Column('data_inicio_ambientacao', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projeto', 'data_inicio_ambientacao')
