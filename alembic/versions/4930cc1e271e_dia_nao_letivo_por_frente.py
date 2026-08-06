"""dia_nao_letivo por frente

Revision ID: 4930cc1e271e
Revises: 28e855351123
Create Date: 2026-08-05 11:21:31.638550

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4930cc1e271e'
down_revision: Union[str, Sequence[str], None] = '28e855351123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """O calendário acadêmico deixa de ser um só e passa a ser por frente.

    Cada frente abrange cursos diferentes, e cada curso tem o seu calendário no
    Insper. `frente_id` NULO segue valendo para todas — é o que preserva a carga
    que já existia e o que cobre o feriado nacional, que não é de curso nenhum.

    ⚠ Ajustado à mão em dois pontos que o --autogenerate erra:

    1. A FK saía com nome `None`, e o downgrade then tentava removê-la por esse
       nome — quebra na hora. Vai nomeada.
    2. A unicidade nova é criada ANTES de a antiga cair. `semestre_id` é o
       primeiro termo das duas, e derrubar a velha primeiro deixa a FK de
       semestre sem índice de apoio por um instante, que é o erro 1553 do MySQL.
    """
    op.add_column('dia_nao_letivo', sa.Column('frente_id', sa.Integer(), nullable=True))
    op.create_index(
        op.f('ix_dia_nao_letivo_frente_id'), 'dia_nao_letivo', ['frente_id'], unique=False
    )
    op.create_unique_constraint(
        'uq_dia_nao_letivo_semestre_frente_data',
        'dia_nao_letivo',
        ['semestre_id', 'frente_id', 'data'],
    )
    op.drop_index(op.f('uq_dia_nao_letivo_semestre_data'), table_name='dia_nao_letivo')
    op.create_foreign_key(
        'fk_dia_nao_letivo_frente', 'dia_nao_letivo', 'frente', ['frente_id'], ['id']
    )


def downgrade() -> None:
    """⚠ Volta é destrutiva: a unicidade antiga é (semestre, data), então dois
    dias iguais em frentes diferentes não cabem nela. As linhas com frente são
    apagadas antes — sobra o calendário global, que é o que existia antes."""
    op.drop_constraint('fk_dia_nao_letivo_frente', 'dia_nao_letivo', type_='foreignkey')
    op.execute("DELETE FROM dia_nao_letivo WHERE frente_id IS NOT NULL")
    op.create_index(
        op.f('uq_dia_nao_letivo_semestre_data'),
        'dia_nao_letivo',
        ['semestre_id', 'data'],
        unique=True,
    )
    op.drop_constraint('uq_dia_nao_letivo_semestre_frente_data', 'dia_nao_letivo', type_='unique')
    op.drop_index(op.f('ix_dia_nao_letivo_frente_id'), table_name='dia_nao_letivo')
    op.drop_column('dia_nao_letivo', 'frente_id')
