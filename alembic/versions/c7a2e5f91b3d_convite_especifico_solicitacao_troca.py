"""convite_especifico_solicitacao_troca

Revision ID: c7a2e5f91b3d
Revises: a1c9f3d7b204
Create Date: 2026-08-06 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7a2e5f91b3d'
down_revision: Union[str, Sequence[str], None] = 'a1c9f3d7b204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('solicitacao_troca', sa.Column('usuario_convidado_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_solicitacao_troca_usuario_convidado',
        'solicitacao_troca', 'usuario',
        ['usuario_convidado_id'], ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_solicitacao_troca_usuario_convidado', 'solicitacao_troca', type_='foreignkey')
    op.drop_column('solicitacao_troca', 'usuario_convidado_id')
