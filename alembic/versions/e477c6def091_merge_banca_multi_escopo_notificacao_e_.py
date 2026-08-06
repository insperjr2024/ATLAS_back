"""merge_banca_multi_escopo_notificacao_e_recuperacao_senha

Revision ID: e477c6def091
Revises: 2ea4aeddacf4, a9267ae28eeb
Create Date: 2026-08-05 18:11:03.334662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e477c6def091'
down_revision: Union[str, Sequence[str], None] = ('2ea4aeddacf4', 'a9267ae28eeb')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
