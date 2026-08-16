"""foto_de_perfil_no_usuario

Revision ID: a1c2d3e4f5b6
Revises: c4a2f7e91b30
Create Date: 2026-08-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT


# revision identifiers, used by Alembic.
revision: str = 'a1c2d3e4f5b6'
down_revision: Union[str, Sequence[str], None] = 'c4a2f7e91b30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'usuario',
        sa.Column('foto', sa.Text().with_variant(MEDIUMTEXT(), 'mysql'), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('usuario', 'foto')
