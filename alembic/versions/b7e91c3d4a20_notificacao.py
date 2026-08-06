"""notificacao

Revision ID: b7e91c3d4a20
Revises: f1a2b3c4d5e6
Create Date: 2026-08-05 18:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e91c3d4a20'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'notificacao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column(
            'tipo',
            sa.Enum(
                'alocado_em_projeto',
                'kickoff_pendente',
                'tarefa_vencida',
                'banca_nao_marcada',
                'projeto_sem_reuniao',
                'banca_hoje',
                'escalacao_banca',
                'entrega_registrada',
                name='tipo_notificacao',
            ),
            nullable=False,
        ),
        sa.Column(
            'origem',
            sa.Enum('evento', 'condicao', name='origem_notificacao'),
            nullable=False,
        ),
        sa.Column('titulo', sa.String(length=200), nullable=False),
        sa.Column('corpo', sa.String(length=500), nullable=True),
        sa.Column('projeto_id', sa.Integer(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('chave_dedup', sa.String(length=120), nullable=False),
        sa.Column('lida_em', sa.DateTime(), nullable=True),
        sa.Column('email_enviado_em', sa.DateTime(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
        sa.ForeignKeyConstraint(['projeto_id'], ['projeto.id'], ),
        sa.PrimaryKeyConstraint('id'),
        # O anti-spam do §6.6, no banco e não só no código: duas passadas
        # concorrentes não conseguem inserir o mesmo alerta duas vezes.
        sa.UniqueConstraint('usuario_id', 'chave_dedup', name='uq_notificacao_usuario_chave'),
    )
    op.create_index(op.f('ix_notificacao_id'), 'notificacao', ['id'], unique=False)
    op.create_index(op.f('ix_notificacao_usuario_id'), 'notificacao', ['usuario_id'], unique=False)
    op.create_index(op.f('ix_notificacao_projeto_id'), 'notificacao', ['projeto_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_notificacao_projeto_id'), table_name='notificacao')
    op.drop_index(op.f('ix_notificacao_usuario_id'), table_name='notificacao')
    op.drop_index(op.f('ix_notificacao_id'), table_name='notificacao')
    op.drop_table('notificacao')
    sa.Enum(name='tipo_notificacao').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='origem_notificacao').drop(op.get_bind(), checkfirst=True)
