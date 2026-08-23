"""calendario por curso dentro da frente

Revision ID: d41a9c73b2e8
Revises: c4f7d20a91e5
Create Date: 2026-08-21

A frente deixa de ser o menor recorte do calendário acadêmico.

A `4930cc1e271e` já tinha escrito o problema no próprio docstring: "cada frente
abrange cursos diferentes, e cada curso tem o seu calendário no Insper". Ela
resolveu metade — separou Business de Tech — e parou onde a frente acaba. A
outra metade aparece dentro da Tech: Ciência da Computação não segue o
calendário das engenharias, e as duas moram na mesma frente. Hoje o PDF de um
sobrescreve o do outro, porque a unicidade é `(semestre, frente, data)`.

`variante` é o nome do calendário dentro da frente. NULO segue valendo para a
frente inteira — é o que preserva Business, Processos e Direito sem tocar em
nada. `frente.calendario_padrao` diz qual variante vale para quem não escolheu,
e `projeto.calendario` é a escolha do diretor de projetos.

A carga de dados no fim é o que mantém os números de hoje intactos: os dias da
Tech viram 'Engenharias' e a Tech passa a ter 'Engenharias' como padrão, então
todo cálculo que não conhece curso continua enxergando exatamente as mesmas 16
datas de antes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd41a9c73b2e8'
down_revision: Union[str, Sequence[str], None] = 'c4f7d20a91e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: O rótulo dado ao calendário que a Tech já tinha carregado. É o das
#: engenharias — o PDF que estava lá — e vira o padrão da frente, para que
#: nenhum projeto mude de resultado ao subir esta migration.
VARIANTE_LEGADA = "Engenharias"


def upgrade() -> None:
    op.add_column('dia_nao_letivo', sa.Column('variante', sa.String(length=30), nullable=True))
    op.add_column('frente', sa.Column('calendario_padrao', sa.String(length=30), nullable=True))
    op.add_column('projeto', sa.Column('calendario', sa.String(length=30), nullable=True))

    # A unicidade nova entra ANTES de a antiga cair, pelo mesmo motivo que a
    # `4930cc1e271e` documenta: `semestre_id` é o primeiro termo das duas, e
    # derrubar a velha primeiro deixa a FK de semestre sem índice de apoio por
    # um instante — o erro 1553 do MySQL.
    #
    # ⚠ Esta constraint é FROUXA, e a `f2b6e1c94a07` logo adiante é que a
    # aperta. Ela ficou assim porque já rodou em produção deste jeito;
    # reescrever o upgrade de uma revisão aplicada não a faria rodar de novo.
    op.create_unique_constraint(
        'uq_dia_nao_letivo_semestre_frente_variante_data',
        'dia_nao_letivo',
        ['semestre_id', 'frente_id', 'variante', 'data'],
    )
    op.drop_constraint(
        'uq_dia_nao_letivo_semestre_frente_data', 'dia_nao_letivo', type_='unique'
    )

    conexao = op.get_bind()

    # Guardado por nome e idempotente: numa base onde a frente não se chama
    # 'Tech' (ou ainda não existe), os dois UPDATEs não pegam linha nenhuma e a
    # migration passa sem efeito, que é o comportamento correto.
    conexao.execute(
        sa.text(
            "UPDATE dia_nao_letivo SET variante = :variante "
            " WHERE frente_id IN (SELECT id FROM frente WHERE nome = 'Tech')"
        ),
        {"variante": VARIANTE_LEGADA},
    )
    conexao.execute(
        sa.text(
            "UPDATE frente SET calendario_padrao = :variante WHERE nome = 'Tech'"
        ),
        {"variante": VARIANTE_LEGADA},
    )


def downgrade() -> None:
    """A volta NÃO apaga linha, ao contrário da `4930cc1e271e`.

    Lá a unicidade antiga era mais estreita que a nova e as linhas com frente
    não cabiam de volta. Aqui elas cabem: sem `variante`, os dias de cada
    calendário viram dias da frente inteira. Duas variantes que marcam a MESMA
    data na mesma frente colidiriam na unicidade antiga, então a colisão é
    desfeita antes, mantendo uma linha por (semestre, frente, data).
    """
    conexao = op.get_bind()
    conexao.execute(
        sa.text(
            "DELETE FROM dia_nao_letivo WHERE id NOT IN ("
            "  SELECT menor FROM ("
            "    SELECT MIN(id) AS menor FROM dia_nao_letivo"
            "     GROUP BY semestre_id, frente_id, data"
            "  ) AS mantidos"
            ")"
        )
    )

    op.create_unique_constraint(
        'uq_dia_nao_letivo_semestre_frente_data',
        'dia_nao_letivo',
        ['semestre_id', 'frente_id', 'data'],
    )
    op.drop_constraint(
        'uq_dia_nao_letivo_semestre_frente_variante_data', 'dia_nao_letivo', type_='unique'
    )

    op.drop_column('projeto', 'calendario')
    op.drop_column('frente', 'calendario_padrao')
    op.drop_column('dia_nao_letivo', 'variante')
