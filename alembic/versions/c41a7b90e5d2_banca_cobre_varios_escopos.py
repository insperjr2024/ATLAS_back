"""banca_cobre_varios_escopos

Uma banca deixa de pertencer a um escopo só. O vínculo sai da coluna
`banca.projeto_escopo_id` e vira a tabela `banca_escopo`, com o UNIQUE do
outro lado: um escopo continua tendo no máximo uma banca, mas uma banca pode
cobrir vários escopos do projeto.

Revision ID: c41a7b90e5d2
Revises: d3a41fddc68d
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c41a7b90e5d2'
down_revision: Union[str, Sequence[str], None] = 'd3a41fddc68d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'banca_escopo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('banca_id', sa.Integer(), nullable=False),
        sa.Column('projeto_escopo_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['banca_id'], ['banca.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['projeto_escopo_id'], ['projeto_escopo.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('projeto_escopo_id', name='uq_banca_escopo_projeto_escopo'),
    )
    op.create_index(op.f('ix_banca_escopo_id'), 'banca_escopo', ['id'], unique=False)
    op.create_index(op.f('ix_banca_escopo_banca_id'), 'banca_escopo', ['banca_id'], unique=False)
    op.create_index(
        op.f('ix_banca_escopo_projeto_escopo_id'), 'banca_escopo', ['projeto_escopo_id'], unique=False
    )

    # ⭐ Backfill antes de derrubar a coluna: cada banca costurada a um escopo
    # vira uma linha aqui. Bancas legadas (projeto_escopo_id nulo) não têm
    # escopo vendido e continuam sem vínculo, como sempre estiveram.
    op.execute(
        "INSERT INTO banca_escopo (banca_id, projeto_escopo_id) "
        "SELECT id, projeto_escopo_id FROM banca WHERE projeto_escopo_id IS NOT NULL"
    )

    op.drop_constraint('fk_banca_projeto_escopo', 'banca', type_='foreignkey')
    op.drop_constraint('uq_banca_projeto_escopo', 'banca', type_='unique')
    op.drop_index(op.f('ix_banca_projeto_escopo_id'), table_name='banca')
    op.drop_column('banca', 'projeto_escopo_id')


def downgrade() -> None:
    """Downgrade schema.

    ⚠ Volta a caber um escopo só por banca: se alguma banca cobria vários, os
    demais vínculos se perdem (fica o de menor id).
    """
    op.add_column('banca', sa.Column('projeto_escopo_id', sa.Integer(), nullable=True))
    op.execute(
        "UPDATE banca b SET projeto_escopo_id = ("
        "  SELECT be.projeto_escopo_id FROM banca_escopo be"
        "  WHERE be.banca_id = b.id ORDER BY be.id LIMIT 1"
        ")"
    )
    op.create_index(op.f('ix_banca_projeto_escopo_id'), 'banca', ['projeto_escopo_id'], unique=False)
    op.create_unique_constraint('uq_banca_projeto_escopo', 'banca', ['projeto_escopo_id'])
    op.create_foreign_key(
        'fk_banca_projeto_escopo', 'banca', 'projeto_escopo', ['projeto_escopo_id'], ['id']
    )

    op.drop_index(op.f('ix_banca_escopo_projeto_escopo_id'), table_name='banca_escopo')
    op.drop_index(op.f('ix_banca_escopo_banca_id'), table_name='banca_escopo')
    op.drop_index(op.f('ix_banca_escopo_id'), table_name='banca_escopo')
    op.drop_table('banca_escopo')
