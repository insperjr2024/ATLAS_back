"""unifica heads: pedido de entrada em banca (main) com contratos

Revision ID: c095d39e2df6
Revises: a4d8e6f01c25, f1a6c3e8b920
Create Date: 2026-09-22 16:54:32.132570

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c095d39e2df6'
down_revision: Union[str, Sequence[str], None] = ('a4d8e6f01c25', 'f1a6c3e8b920')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
