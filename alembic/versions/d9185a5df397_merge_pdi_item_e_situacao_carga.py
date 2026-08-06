"""merge_pdi_item_e_situacao_carga

Revision ID: d9185a5df397
Revises: 21adfe0d3a5c, 26b5ab871976
Create Date: 2026-08-06 16:09:30.989599

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9185a5df397'
down_revision: Union[str, Sequence[str], None] = ('21adfe0d3a5c', '26b5ab871976')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
