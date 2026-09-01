"""calendario base por escopo

Revision ID: e5c1a9f37b64
Revises: b7d4e2a10c58
Create Date: 2026-08-31

O calendário acadêmico deixa de ser um override do PROJETO e vira a BASE do
ESCOPO.

A `d41a9c73b2e8` criou `projeto.calendario` como escolha opcional: nulo =
"segue o padrão da frente". Foi desenhado para um caso só — a Tech cobre
engenharias e Ciência da Computação —, e por isso ficou opcional. O efeito é
que ninguém nunca escolheu: os 22 projetos em produção estão todos nulos, e o
seletor do front nem aparece nas frentes que têm um calendário só.

Pior, a escolha não filtrava nada. `filtrar_variante` corta por VARIANTE e
nunca por frente, então todo projeto contava a união dos dias de todas as
frentes — um projeto de Business parava na semana de avaliação da Tech.

Agora cada escopo declara o calendário que segue. `projeto_escopo.frente_id` já
é NOT NULL, então o par (frente, calendário) identifica exatamente um
calendário base. Nulo continua sendo legítimo: é o calendário da frente que tem
um só (Business, Direito, Processos), o mesmo nulo de `dia_nao_letivo.variante`
— quem obriga a escolher é o cadastro, não a coluna, porque não há rótulo a
inventar para uma frente de curso único.

A carga preserva os números: cada escopo herda `frente.calendario_padrao` da
frente dele, que para a Tech é 'Engenharias' e para as demais é nulo. Nenhuma
data de janela se move (conferido contra os 16 escopos iniciados em produção).

`projeto.calendario` sai: todos os 22 valores são nulos, então não há dado a
perder, e mantê-la deixaria duas fontes para a mesma pergunta.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5c1a9f37b64'
down_revision: Union[str, Sequence[str], None] = 'b7d4e2a10c58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'projeto_escopo', sa.Column('calendario', sa.String(length=30), nullable=True)
    )
    # Cada escopo herda o padrão da frente dele. É o que mantém a Tech em
    # 'Engenharias' e as outras no calendário único delas.
    op.execute(
        """
        UPDATE projeto_escopo
           SET calendario = (
               SELECT f.calendario_padrao FROM frente f WHERE f.id = projeto_escopo.frente_id
           )
        """
    )
    op.drop_column('projeto', 'calendario')


def downgrade() -> None:
    op.add_column('projeto', sa.Column('calendario', sa.String(length=30), nullable=True))
    # O caminho de volta não reconstrói a escolha por escopo num campo só de
    # projeto: um projeto sinérgico tem dois calendários e não cabe em uma
    # coluna. Volta nulo, que é como os 22 projetos estavam.
    op.drop_column('projeto_escopo', 'calendario')
