"""projeto_vendedor

Revision ID: b8e3f1a56c04
Revises: a7c1e4b93f02
Create Date: 2026-08-20

Registra QUEM VENDEU cada projeto.

O dado da venda já existia espalhado pelo cadastro — `status='vendido'`,
`dias_uteis_vendidos` (o "registro comercial"), cliente, proposta, a data
prometida. O que nunca existiu foi o dono: não havia como responder "quem
trouxe este projeto".

Tabela nova em vez de um terceiro valor em `projeto_membro.papel`: aquele enum
é lido por 20 use cases (capacidade, o bloqueio do §8, Avaliação de
Desempenho, painel de equipe), e um papel a mais mudaria todos em silêncio.
Vender não é executar.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8e3f1a56c04'
down_revision: Union[str, Sequence[str], None] = 'a7c1e4b93f02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'projeto_vendedor',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('projeto_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('registrado_em', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('registrado_por', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['projeto_id'], ['projeto.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id']),
        sa.ForeignKeyConstraint(['registrado_por'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('projeto_id', 'usuario_id', name='uq_projeto_vendedor'),
    )
    op.create_index(op.f('ix_projeto_vendedor_id'), 'projeto_vendedor', ['id'], unique=False)
    op.create_index(
        op.f('ix_projeto_vendedor_projeto_id'), 'projeto_vendedor', ['projeto_id'], unique=False
    )
    op.create_index(
        op.f('ix_projeto_vendedor_usuario_id'), 'projeto_vendedor', ['usuario_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_projeto_vendedor_usuario_id'), table_name='projeto_vendedor')
    op.drop_index(op.f('ix_projeto_vendedor_projeto_id'), table_name='projeto_vendedor')
    op.drop_index(op.f('ix_projeto_vendedor_id'), table_name='projeto_vendedor')
    op.drop_table('projeto_vendedor')
