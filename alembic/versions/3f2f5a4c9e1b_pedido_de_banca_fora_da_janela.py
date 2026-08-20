"""pedido de banca fora da janela

Revision ID: 3f2f5a4c9e1b
Revises: 7cd394623af4
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f2f5a4c9e1b'
down_revision: Union[str, Sequence[str], None] = '7cd394623af4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('banca_fora_janela_solicitacao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('projeto_escopo_id', sa.Integer(), nullable=False),
    sa.Column('banca_id', sa.Integer(), nullable=True),
    sa.Column('data_hora_pretendida', sa.DateTime(), nullable=False),
    sa.Column('justificativa', sa.String(length=500), nullable=False),
    sa.Column('status', sa.Enum('pendente', 'aprovada', 'recusada', name='status_fora_janela'), server_default='pendente', nullable=False),
    sa.Column('solicitado_por', sa.Integer(), nullable=False),
    sa.Column('respondido_por', sa.Integer(), nullable=True),
    sa.Column('resposta', sa.String(length=500), nullable=True),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('respondido_em', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['banca_id'], ['banca.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['projeto_escopo_id'], ['projeto_escopo.id'], ),
    sa.ForeignKeyConstraint(['respondido_por'], ['usuario.id'], ),
    sa.ForeignKeyConstraint(['solicitado_por'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_banca_fora_janela_solicitacao_banca_id'), 'banca_fora_janela_solicitacao', ['banca_id'], unique=False)
    op.create_index(op.f('ix_banca_fora_janela_solicitacao_data_hora_pretendida'), 'banca_fora_janela_solicitacao', ['data_hora_pretendida'], unique=False)
    op.create_index(op.f('ix_banca_fora_janela_solicitacao_id'), 'banca_fora_janela_solicitacao', ['id'], unique=False)
    op.create_index(op.f('ix_banca_fora_janela_solicitacao_projeto_escopo_id'), 'banca_fora_janela_solicitacao', ['projeto_escopo_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_banca_fora_janela_solicitacao_projeto_escopo_id'), table_name='banca_fora_janela_solicitacao')
    op.drop_index(op.f('ix_banca_fora_janela_solicitacao_id'), table_name='banca_fora_janela_solicitacao')
    op.drop_index(op.f('ix_banca_fora_janela_solicitacao_data_hora_pretendida'), table_name='banca_fora_janela_solicitacao')
    op.drop_index(op.f('ix_banca_fora_janela_solicitacao_banca_id'), table_name='banca_fora_janela_solicitacao')
    op.drop_table('banca_fora_janela_solicitacao')
