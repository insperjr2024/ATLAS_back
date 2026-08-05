"""split_permissoes_cargo

Revision ID: 16ccf74cebdd
Revises: 0cd1a5deb16f
Create Date: 2026-08-05 10:42:58.672606

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16ccf74cebdd'
down_revision: Union[str, Sequence[str], None] = '0cd1a5deb16f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Quebra o antigo `pode_gerenciar_cargos` em três capacidades.

    Ele sozinho abria Configurações, Núcleo e Membros de uma vez. O backfill
    dá as três a quem já tinha a flag, para nenhum cargo existente perder
    acesso na migração — a separação só passa a valer daí em diante.
    """
    op.add_column(
        "cargo",
        sa.Column("pode_gerenciar_membros", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "cargo",
        sa.Column("pode_gerenciar_nucleo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE cargo SET pode_gerenciar_membros = 1, pode_gerenciar_nucleo = 1 "
        "WHERE pode_gerenciar_cargos = 1"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("cargo", "pode_gerenciar_nucleo")
    op.drop_column("cargo", "pode_gerenciar_membros")
