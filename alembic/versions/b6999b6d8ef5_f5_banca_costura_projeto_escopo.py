"""f5_banca_costura_projeto_escopo

Revision ID: b6999b6d8ef5
Revises: dc5bc4321c2c
Create Date: 2026-08-04 14:15:56.544438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'b6999b6d8ef5'
down_revision: Union[str, Sequence[str], None] = 'dc5bc4321c2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('banca', sa.Column('projeto_escopo_id', sa.Integer(), nullable=True))
    op.add_column('banca', sa.Column('realizado_em', sa.DateTime(), nullable=True))
    op.add_column('banca', sa.Column('resultado', sa.Enum('aprovada', 'nao_aprovada', name='resultado_banca'), nullable=True))
    op.add_column('banca', sa.Column('excecao_choque_por', sa.Integer(), nullable=True))
    op.add_column('banca', sa.Column('excecao_choque_nota', sa.String(length=255), nullable=True))
    op.alter_column('banca', 'escopo_id',
               existing_type=mysql.INTEGER(),
               nullable=True)
    op.alter_column('banca', 'data_hora',
               existing_type=mysql.DATETIME(),
               nullable=True)
    op.create_index(op.f('ix_banca_projeto_escopo_id'), 'banca', ['projeto_escopo_id'], unique=False)
    # UNIQUE em coluna nullable funciona a favor: o MySQL permite N linhas com
    # NULL, então todas as bancas legadas (sem escopo vendido) convivem.
    op.create_unique_constraint('uq_banca_projeto_escopo', 'banca', ['projeto_escopo_id'])
    op.create_foreign_key('fk_banca_projeto_escopo', 'banca', 'projeto_escopo', ['projeto_escopo_id'], ['id'])
    op.create_foreign_key('fk_banca_excecao_choque_por', 'banca', 'usuario', ['excecao_choque_por'], ['id'])

    # ⭐ BACKFILL — a linha que torna a reescrita de `banca_status.py`
    # retrocompatível, e que o --autogenerate nunca geraria.
    #
    # Até aqui, "realizada" era inferido do relógio: data passada = realizada.
    # Com os 4 estados novos, toda banca passada sem `realizado_em` viraria
    # `atrasada` — e três consumidores do módulo de Avaliação (P2) filtram por
    # "realizada": filtrar_historico_bancas, desempenho_consultor e
    # avaliacoes_pendentes. Sem este UPDATE, o histórico de bancas volta
    # vazio, todo mundo aparece com 0% de desempenho e ninguém mais recebe
    # avaliação pendente.
    op.execute(
        "UPDATE banca SET realizado_em = data_hora "
        "WHERE data_hora IS NOT NULL AND data_hora < NOW() AND realizado_em IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema.

    ⚠ Restaurar NOT NULL em `data_hora`/`escopo_id` falha se já existir linha
    com o campo vazio (banca não marcada, escopo "Outro"). É aceitável —
    downgrade é ferramenta de dev — mas limpe essas linhas antes de rodar.
    """
    op.drop_constraint('fk_banca_excecao_choque_por', 'banca', type_='foreignkey')
    op.drop_constraint('fk_banca_projeto_escopo', 'banca', type_='foreignkey')
    op.drop_constraint('uq_banca_projeto_escopo', 'banca', type_='unique')
    op.drop_index(op.f('ix_banca_projeto_escopo_id'), table_name='banca')
    op.alter_column('banca', 'data_hora',
               existing_type=mysql.DATETIME(),
               nullable=False)
    op.alter_column('banca', 'escopo_id',
               existing_type=mysql.INTEGER(),
               nullable=False)
    op.drop_column('banca', 'excecao_choque_nota')
    op.drop_column('banca', 'excecao_choque_por')
    op.drop_column('banca', 'resultado')
    op.drop_column('banca', 'realizado_em')
    op.drop_column('banca', 'projeto_escopo_id')
    # ### end Alembic commands ###
