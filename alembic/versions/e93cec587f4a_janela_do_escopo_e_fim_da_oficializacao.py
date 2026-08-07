"""janela_do_escopo_e_fim_da_oficializacao

A reformulação do cronograma, num só lugar porque as cinco mudanças são a
mesma decisão de produto e separá-las deixaria o banco num estado incoerente
no meio do caminho (escopo com dias ajustados mas ainda com o cadeado de
oficialização, por exemplo).

1. `projeto_escopo.dias_uteis_ajustados` — os dias extras autorizados. Zero
   para todo mundo que já existe, o que mantém a janela igual aos dias
   vendidos e não muda nenhum número de projeto em andamento.
2. `projeto_escopo.cronograma_oficializado_em` **sai** — o cadeado acabou.
   ⚠ Irreversível na prática: o `downgrade` recria a coluna, mas vazia; quem
   estava oficializado não volta a estar.
3. `cronograma_reajuste_solicitacao.dias_solicitados` — a tabela deixou de
   pedir "reabertura de cronograma" e passou a pedir DIAS. As linhas antigas
   ficam com zero e viram registro histórico.
4. `reuniao_semanal.observacoes` + o UNIQUE passa a incluir o escopo: reunião
   inicial e reunião geral agora são marcadas no mesmo calendário e precisam
   caber no mesmo dia.
5. `banca_remarcacao` — a data antiga de cada remarcação, que hoje só existe
   na notificação e some quando ela é lida.

Revision ID: e93cec587f4a
Revises: f20cbf22f5ee
Create Date: 2026-08-06 20:44:54.018222

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'e93cec587f4a'
down_revision: Union[str, Sequence[str], None] = 'f20cbf22f5ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'banca_remarcacao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('banca_id', sa.Integer(), nullable=False),
        sa.Column('data_anterior', sa.DateTime(), nullable=True),
        sa.Column('data_nova', sa.DateTime(), nullable=False),
        sa.Column('justificativa', sa.String(length=500), nullable=False),
        sa.Column('remarcado_por', sa.Integer(), nullable=False),
        sa.Column('autorizado_por', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['autorizado_por'], ['usuario.id'], ),
        sa.ForeignKeyConstraint(['banca_id'], ['banca.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['remarcado_por'], ['usuario.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_banca_remarcacao_banca_id'), 'banca_remarcacao', ['banca_id'], unique=False
    )
    op.create_index(op.f('ix_banca_remarcacao_id'), 'banca_remarcacao', ['id'], unique=False)

    # server_default à mão nas duas: as tabelas já têm linhas, e NOT NULL sem
    # default falha (mesmo motivo da migration de permissões de cargo).
    #
    # ⚠ Condicional por causa da ORDEM DO GRAFO depois do merge com a main.
    # Numa base que já existia, a tabela está aqui e a coluna é adicionada
    # normalmente. Mas numa base NOVA a cadeia passa antes por
    # `72a7a5145a5a` (o revert da main), que DROPA a tabela — e aí este
    # ALTER estourava com 1146, deixando o schema impossível de construir do
    # zero. Quem repõe a tabela é `b1c4d7e90a22`, mais adiante, e ela já a
    # cria com `dias_solicitados` dentro. Então aqui basta não atrapalhar.
    if 'cronograma_reajuste_solicitacao' in sa.inspect(op.get_bind()).get_table_names():
        op.add_column(
            'cronograma_reajuste_solicitacao',
            sa.Column('dias_solicitados', sa.Integer(), nullable=False, server_default='0'),
        )
    op.add_column(
        'projeto_escopo',
        sa.Column('dias_uteis_ajustados', sa.Integer(), nullable=False, server_default='0'),
    )
    op.drop_column('projeto_escopo', 'cronograma_oficializado_em')

    op.add_column('reuniao_semanal', sa.Column('observacoes', sa.String(length=500), nullable=True))
    op.drop_constraint(op.f('uq_reuniao_projeto_data'), 'reuniao_semanal', type_='unique')
    op.create_unique_constraint(
        'uq_reuniao_projeto_data',
        'reuniao_semanal',
        ['projeto_id', 'data_reuniao', 'projeto_escopo_id'],
    )


def downgrade() -> None:
    """Downgrade schema.

    ⚠ O UNIQUE volta a ser (projeto, data): se alguém tiver marcado duas
    reuniões no mesmo dia enquanto a versão nova estava no ar, este passo falha
    — e falhar é o certo, porque apagar a reunião "sobrando" seria escolher
    sozinho qual das duas o time perde.
    """
    op.drop_constraint('uq_reuniao_projeto_data', 'reuniao_semanal', type_='unique')
    op.create_unique_constraint(
        op.f('uq_reuniao_projeto_data'), 'reuniao_semanal', ['projeto_id', 'data_reuniao']
    )
    op.drop_column('reuniao_semanal', 'observacoes')

    # Recriada vazia: o carimbo de quem já estava oficializado não volta.
    op.add_column(
        'projeto_escopo', sa.Column('cronograma_oficializado_em', mysql.DATETIME(), nullable=True)
    )
    op.drop_column('projeto_escopo', 'dias_uteis_ajustados')
    if 'cronograma_reajuste_solicitacao' in sa.inspect(op.get_bind()).get_table_names():
        op.drop_column('cronograma_reajuste_solicitacao', 'dias_solicitados')

    op.drop_index(op.f('ix_banca_remarcacao_id'), table_name='banca_remarcacao')
    op.drop_index(op.f('ix_banca_remarcacao_banca_id'), table_name='banca_remarcacao')
    op.drop_table('banca_remarcacao')
