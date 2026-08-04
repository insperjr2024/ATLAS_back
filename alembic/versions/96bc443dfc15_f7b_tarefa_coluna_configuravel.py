"""f7b_tarefa_coluna_configuravel

As colunas do kanban deixam de ser um ENUM no código e viram dados, para a
diretoria montar o próprio fluxo (renomear, recolorir, reordenar, criar).

⚠ O `--autogenerate` propôs "adiciona coluna_id NOT NULL + dropa status",
que falharia na primeira linha existente e jogaria fora o status de toda
tarefa já criada. A conversão abaixo é manual e em 5 tempos:

    1. cria `tarefa_coluna`
    2. semeia as 5 colunas que eram o ENUM, com as cores que já estavam na
       tela — o board de quem já usa continua idêntico
    3. adiciona `tarefa.coluna_id` NULLABLE
    4. converte cada tarefa pelo status antigo
    5. só então NOT NULL + dropa `status`

Revision ID: 96bc443dfc15
Revises: d0b3af873672
Create Date: 2026-08-04 16:27:27.402128
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = '96bc443dfc15'
down_revision: Union[str, Sequence[str], None] = 'd0b3af873672'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: (chave, nome, cor, ordem, encerra_tarefa) — o ENUM antigo, virando dado.
#: As cores são as mesmas que o front já desenhava.
COLUNAS_PADRAO = [
    ("a_fazer", "A fazer", "#9CA3AF", 0, False),
    ("em_andamento", "Em andamento", "#3B82F6", 1, False),
    ("validacao", "Validação", "#F59E0B", 2, False),
    ("concluido", "Concluído", "#10B981", 3, True),
    ("cancelado", "Cancelado", "#EF4444", 4, True),
]


def upgrade() -> None:
    tarefa_coluna = op.create_table(
        'tarefa_coluna',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chave', sa.String(length=30), nullable=True),
        sa.Column('nome', sa.String(length=60), nullable=False),
        sa.Column('cor', sa.String(length=7), nullable=False),
        sa.Column('ordem', sa.SmallInteger(), server_default='0', nullable=False),
        sa.Column('encerra_tarefa', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chave'),
    )
    op.create_index(op.f('ix_tarefa_coluna_id'), 'tarefa_coluna', ['id'], unique=False)

    # 2 · As 5 colunas que eram o ENUM.
    op.bulk_insert(
        tarefa_coluna,
        [
            {"chave": chave, "nome": nome, "cor": cor, "ordem": ordem, "encerra_tarefa": encerra}
            for chave, nome, cor, ordem, encerra in COLUNAS_PADRAO
        ],
    )

    # 3 · Nullable primeiro: a tabela pode já ter tarefas.
    op.add_column('tarefa', sa.Column('coluna_id', sa.Integer(), nullable=True))

    # 4 · ⭐ A conversão. Sem ela, toda tarefa existente perderia a coluna.
    op.execute(
        "UPDATE tarefa t JOIN tarefa_coluna c ON c.chave = t.status "
        "SET t.coluna_id = c.id"
    )
    # Rede de segurança: qualquer linha com status fora do ENUM (não deveria
    # existir) cai em "A fazer" em vez de bloquear a migration inteira.
    op.execute(
        "UPDATE tarefa SET coluna_id = "
        "(SELECT id FROM tarefa_coluna WHERE chave = 'a_fazer') "
        "WHERE coluna_id IS NULL"
    )

    # 5 · Agora sim.
    op.alter_column('tarefa', 'coluna_id', existing_type=sa.Integer(), nullable=False)
    op.create_index('ix_tarefa_coluna_id_fk', 'tarefa', ['coluna_id'], unique=False)
    op.create_foreign_key('fk_tarefa_coluna', 'tarefa', 'tarefa_coluna', ['coluna_id'], ['id'])
    op.drop_column('tarefa', 'status')


def downgrade() -> None:
    """⚠ Volta perde as colunas criadas pela diretoria: o ENUM só comporta as
    5 originais, e tarefa em coluna customizada cai em 'a_fazer'."""
    op.add_column(
        'tarefa',
        sa.Column(
            'status',
            mysql.ENUM('a_fazer', 'em_andamento', 'validacao', 'concluido', 'cancelado',
                       collation='utf8mb4_unicode_ci'),
            server_default=sa.text("'a_fazer'"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE tarefa t JOIN tarefa_coluna c ON c.id = t.coluna_id "
        "SET t.status = c.chave WHERE c.chave IS NOT NULL"
    )
    op.drop_constraint('fk_tarefa_coluna', 'tarefa', type_='foreignkey')
    op.drop_index('ix_tarefa_coluna_id_fk', table_name='tarefa')
    op.drop_column('tarefa', 'coluna_id')
    op.drop_index(op.f('ix_tarefa_coluna_id'), table_name='tarefa_coluna')
    op.drop_table('tarefa_coluna')
