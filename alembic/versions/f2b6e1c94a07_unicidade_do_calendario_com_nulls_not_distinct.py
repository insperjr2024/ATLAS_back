"""unicidade do calendario com nulls not distinct

Revision ID: f2b6e1c94a07
Revises: d41a9c73b2e8
Create Date: 2026-08-21

Aperta a unicidade que a `d41a9c73b2e8` deixou frouxa.

Ela criou `UNIQUE (semestre_id, frente_id, variante, data)` e, no Postgres,
isso **não protege quase nada**: dois NULLs são considerados distintos, e
`variante` é nula em 29 das 45 linhas de hoje — toda linha sem calendário de
curso escapava da constraint. Pior que a situação anterior, em que ao menos as
linhas com frente eram cobertas.

`NULLS NOT DISTINCT` (Postgres 15+, a base roda 17.6) restaura a proteção e
ainda fecha um buraco antigo: a constraint passa a valer também para as linhas
globais (`frente_id` nulo), que a unicidade de antes já deixava passar. Fora do
Postgres nada muda, e a deduplicação de `create_dia_nao_letivo` segue sendo a
rede — como sempre foi.

Vem em revisão separada, e não como correção da `d41a9c73b2e8`, porque aquela
já rodou: reescrever o `upgrade` de uma revisão aplicada não a faz rodar de
novo, e o banco ficaria diferente do que o arquivo diz.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f2b6e1c94a07'
down_revision: Union[str, Sequence[str], None] = 'd41a9c73b2e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOME = "uq_dia_nao_letivo_semestre_frente_variante_data"
COLUNAS = "(semestre_id, frente_id, variante, data)"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    # Se sobrou duplicata do período em que a constraint não pegava, ela
    # impediria a nova de nascer — e o erro sairia sem dizer onde está o
    # problema. Apurar antes deixa a mensagem útil.
    duplicatas = op.get_bind().execute(
        sa.text(
            "SELECT semestre_id, frente_id, variante, data, COUNT(*) "
            "  FROM dia_nao_letivo "
            " GROUP BY semestre_id, frente_id, variante, data "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicatas:
        raise RuntimeError(
            "Há dias não letivos repetidos e a unicidade nova não cabe sobre eles. "
            f"Resolva antes: {duplicatas}"
        )

    op.execute(f"ALTER TABLE dia_nao_letivo DROP CONSTRAINT {NOME}")
    op.execute(
        f"ALTER TABLE dia_nao_letivo ADD CONSTRAINT {NOME} "
        f"UNIQUE NULLS NOT DISTINCT {COLUNAS}"
    )


def downgrade() -> None:
    """Volta para a unicidade frouxa. Não perde linha: ela aceita tudo o que a
    apertada aceitava, e mais."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f"ALTER TABLE dia_nao_letivo DROP CONSTRAINT {NOME}")
    op.execute(f"ALTER TABLE dia_nao_letivo ADD CONSTRAINT {NOME} UNIQUE {COLUNAS}")
