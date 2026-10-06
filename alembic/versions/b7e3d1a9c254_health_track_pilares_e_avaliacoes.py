"""health_track_pilares_e_avaliacoes

Health Track §2 e §3: os pilares (dados editáveis pela diretoria, nunca
fixos no código) e a avaliação por projeto + pilar + data, que só cresce.

Os 6 pilares iniciais são semeados aqui, como as colunas do kanban em
`96bc443dfc15` — sem eles a tela abriria sem nada para avaliar.

Revision ID: b7e3d1a9c254
Revises: f1a9c47db235
Create Date: 2026-10-05 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b7e3d1a9c254'
down_revision: Union[str, Sequence[str], None] = 'f1a9c47db235'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: (nome, descrição) na ordem de exibição da spec (§2).
PILARES_INICIAIS = [
    (
        "Cronograma & Prazos",
        "Avalia se o projeto está avançando de acordo com o planejamento e se marcos, "
        "entregas, bancas e demais prazos estão sendo cumpridos.",
    ),
    (
        "Cliente",
        "Avalia a saúde da relação com o cliente, considerando comunicação, responsividade, "
        "alinhamento de expectativas, satisfação e possíveis conflitos.",
    ),
    (
        "Escopo",
        "Avalia se o projeto continua aderente ao que foi vendido e acordado, incluindo "
        "mudanças de escopo, pedidos adicionais, ambiguidades e risco de scope creep.",
    ),
    (
        "Qualidade",
        "Avalia a qualidade do trabalho produzido, considerando profundidade das análises, "
        "consistência, aderência ao objetivo do projeto e necessidade de retrabalho.",
    ),
    (
        "Equipe",
        "Avalia a capacidade da equipe de executar o projeto, considerando engajamento, "
        "disponibilidade, organização, colaboração, divisão de responsabilidades e "
        "possíveis dificuldades internas.",
    ),
    (
        "Desenvolvimento",
        "Avalia se o projeto está cumprindo seu papel de desenvolver os membros da JR, "
        "considerando aprendizado, autonomia, feedback, exposição a responsabilidades "
        "relevantes e desenvolvimento de competências.",
    ),
]


def upgrade() -> None:
    health_track_pilar = op.create_table(
        'health_track_pilar',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=60), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('ordem', sa.SmallInteger(), server_default='0', nullable=False),
        sa.Column('ativo', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nome'),
    )
    op.create_index(op.f('ix_health_track_pilar_id'), 'health_track_pilar', ['id'], unique=False)

    op.bulk_insert(
        health_track_pilar,
        [
            {"nome": nome, "descricao": descricao, "ordem": ordem, "ativo": True}
            for ordem, (nome, descricao) in enumerate(PILARES_INICIAIS)
        ],
    )

    op.create_table(
        'health_track_avaliacao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('projeto_id', sa.Integer(), nullable=False),
        sa.Column('pilar_id', sa.Integer(), nullable=False),
        sa.Column('cor', sa.Enum('verde', 'amarelo', 'vermelho', name='cor_health_track'), nullable=False),
        sa.Column('comentario', sa.Text(), nullable=True),
        sa.Column('avaliado_por', sa.Integer(), nullable=False),
        sa.Column('avaliado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['projeto_id'], ['projeto.id']),
        sa.ForeignKeyConstraint(['pilar_id'], ['health_track_pilar.id']),
        sa.ForeignKeyConstraint(['avaliado_por'], ['usuario.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_health_track_avaliacao_id'), 'health_track_avaliacao', ['id'], unique=False)
    op.create_index(op.f('ix_health_track_avaliacao_projeto_id'), 'health_track_avaliacao', ['projeto_id'], unique=False)
    op.create_index(op.f('ix_health_track_avaliacao_pilar_id'), 'health_track_avaliacao', ['pilar_id'], unique=False)
    op.create_index(
        'ix_health_track_avaliacao_projeto_pilar_data',
        'health_track_avaliacao',
        ['projeto_id', 'pilar_id', 'avaliado_em'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_health_track_avaliacao_projeto_pilar_data', table_name='health_track_avaliacao')
    op.drop_index(op.f('ix_health_track_avaliacao_pilar_id'), table_name='health_track_avaliacao')
    op.drop_index(op.f('ix_health_track_avaliacao_projeto_id'), table_name='health_track_avaliacao')
    op.drop_index(op.f('ix_health_track_avaliacao_id'), table_name='health_track_avaliacao')
    op.drop_table('health_track_avaliacao')
    sa.Enum(name='cor_health_track').drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f('ix_health_track_pilar_id'), table_name='health_track_pilar')
    op.drop_table('health_track_pilar')
