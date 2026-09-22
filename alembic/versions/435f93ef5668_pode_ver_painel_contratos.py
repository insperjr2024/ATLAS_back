"""pode_ver_painel_contratos

Revision ID: 435f93ef5668
Revises: bd8634cfbd95
Create Date: 2026-09-21 19:32:12.349437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '435f93ef5668'
down_revision: Union[str, Sequence[str], None] = 'bd8634cfbd95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "posicao_permissao",
        sa.Column("pode_ver_painel_contratos", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("posicao_permissao", "pode_ver_painel_contratos")
