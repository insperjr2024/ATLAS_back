"""merge_banca_multi_escopo_e_notificacao_troca

Revision ID: 2ea4aeddacf4
Revises: 73fcb381a784, c41a7b90e5d2
Create Date: 2026-08-05 17:34:05.185727

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ea4aeddacf4'
down_revision: Union[str, Sequence[str], None] = ('73fcb381a784', 'c41a7b90e5d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
