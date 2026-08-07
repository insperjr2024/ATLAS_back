"""cargo_pode_ver_todos_projetos

Revision ID: 8d3962297df7
Revises: deda213224f9
Create Date: 2026-08-07 02:58:09.709730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d3962297df7'
down_revision: Union[str, Sequence[str], None] = 'deda213224f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'cargo',
        sa.Column('pode_ver_todos_projetos', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Nota: o autogenerate também detectou a mesma renomeação de índice de
    # `tarefa_coluna` de sempre — ruído antigo de portabilidade, sem relação
    # com esta migration, removido daqui de propósito.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('cargo', 'pode_ver_todos_projetos')
