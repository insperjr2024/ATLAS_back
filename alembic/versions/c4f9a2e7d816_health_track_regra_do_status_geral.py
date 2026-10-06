"""health_track_regra_do_status_geral

Health Track §5: os parâmetros que transformam as cores dos pilares no status
geral do projeto saem do código e viram dado editável pela diretoria de
projetos. Cada edição é uma versão nova com data de vigência; a anterior não
é tocada.

A versão inicial (a regra do §4, com o "mínimo de vermelhos: 1" do §5) nasce
com vigência no passado, para cobrir todo ciclo já preenchido.

Revision ID: c4f9a2e7d816
Revises: b7e3d1a9c254
Create Date: 2026-10-05 15:00:00.000000
"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c4f9a2e7d816'
down_revision: Union[str, Sequence[str], None] = 'b7e3d1a9c254'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    health_track_regra = op.create_table(
        'health_track_regra',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('verde_max_amarelos', sa.Integer(), nullable=False),
        sa.Column('verde_max_vermelhos', sa.Integer(), nullable=False),
        sa.Column('vermelho_min_amarelos', sa.Integer(), nullable=False),
        sa.Column('vermelho_min_vermelhos', sa.Integer(), nullable=False),
        sa.Column('vigente_desde', sa.DateTime(), nullable=False),
        sa.Column('criado_por', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['criado_por'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_health_track_regra_id'), 'health_track_regra', ['id'], unique=False)
    op.create_index(op.f('ix_health_track_regra_vigente_desde'), 'health_track_regra', ['vigente_desde'], unique=False)

    op.bulk_insert(
        health_track_regra,
        [
            {
                "verde_max_amarelos": 1,
                "verde_max_vermelhos": 0,
                "vermelho_min_amarelos": 3,
                "vermelho_min_vermelhos": 1,
                "vigente_desde": datetime(2000, 1, 1),
                "criado_por": None,
            }
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_health_track_regra_vigente_desde'), table_name='health_track_regra')
    op.drop_index(op.f('ix_health_track_regra_id'), table_name='health_track_regra')
    op.drop_table('health_track_regra')
