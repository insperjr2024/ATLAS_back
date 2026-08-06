"""reuniao_semanal_por_escopo

A reunião semanal passa a dizer sobre QUAL escopo foi — é o vínculo que faz
`projeto_escopo.data_inicio` nascer da reunião inicial (§5.4), em vez de um
campo digitado à parte.

Nulo de propósito: reunião geral do projeto (sem escopo) continua válida, e as
linhas antigas ficam exatamente como estão.

Revision ID: a1c7e4b93d20
Revises: d81e5a2c9f37
Create Date: 2026-08-06 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c7e4b93d20'
down_revision: Union[str, Sequence[str], None] = 'd81e5a2c9f37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'reuniao_semanal', sa.Column('projeto_escopo_id', sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f('ix_reuniao_semanal_projeto_escopo_id'),
        'reuniao_semanal',
        ['projeto_escopo_id'],
        unique=False,
    )
    op.create_foreign_key(
        'fk_reuniao_semanal_projeto_escopo',
        'reuniao_semanal',
        'projeto_escopo',
        ['projeto_escopo_id'],
        ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'fk_reuniao_semanal_projeto_escopo', 'reuniao_semanal', type_='foreignkey'
    )
    op.drop_index(
        op.f('ix_reuniao_semanal_projeto_escopo_id'), table_name='reuniao_semanal'
    )
    op.drop_column('reuniao_semanal', 'projeto_escopo_id')
