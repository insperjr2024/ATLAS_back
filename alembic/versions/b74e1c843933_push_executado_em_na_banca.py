"""push_executado_em_na_banca

Revision ID: b74e1c843933
Revises: a9cae5c30c6d
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b74e1c843933'
down_revision: Union[str, Sequence[str], None] = 'a9cae5c30c6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('banca', sa.Column('push_executado_em', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('banca', 'push_executado_em')
