"""unifica heads cargo permissoes e senha provisoria

Revision ID: addea83280e5
Revises: f4a2c8e01b93, f81c58ed626c
Create Date: 2026-08-06 21:39:30.352688

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'addea83280e5'
down_revision: Union[str, Sequence[str], None] = ('f4a2c8e01b93', 'f81c58ed626c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
