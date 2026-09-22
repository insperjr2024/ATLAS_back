"""contrato_institucional_sem_projeto

Revision ID: 9c1e5a7d3f42
Revises: f8a2c4de91b7
Create Date: 2026-09-21 21:15:00.000000

⭐ 2026-09-21 — reverte a abordagem anterior (`743e671bffea`, `projeto.
institucional`): um contrato institucional (Agro etc.) não deveria criar um
`ProjetoModel` só pra existir — é um documento avulso, de um "projeto" que
não é da Júnior, só um nome digitado no formulário. `documento_contratual.
projeto_id` vira nullable, com `nome_projeto_externo`/`cliente_externo`
preenchidos só quando não há projeto de verdade por trás.

A UNIQUE CONSTRAINT original (`uq_documento_contratual_projeto_tipo`) vira
um ÍNDICE único parcial — Postgres não aceita `WHERE` numa constraint, só
num índice — pra deixar explícito que "um documento de cada tipo por
projeto" só vale pra quem TEM projeto.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9c1e5a7d3f42'
down_revision: Union[str, Sequence[str], None] = 'f8a2c4de91b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documento_contratual", sa.Column("nome_projeto_externo", sa.String(150), nullable=True))
    op.add_column("documento_contratual", sa.Column("cliente_externo", sa.String(150), nullable=True))

    op.drop_constraint(
        "uq_documento_contratual_projeto_tipo", "documento_contratual", type_="unique"
    )
    op.alter_column("documento_contratual", "projeto_id", nullable=True)

    op.create_index(
        "uq_documento_contratual_projeto_tipo",
        "documento_contratual",
        ["projeto_id", "tipo"],
        unique=True,
        postgresql_where=sa.text("projeto_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_documento_contratual_projeto_tipo", table_name="documento_contratual")
    op.alter_column("documento_contratual", "projeto_id", nullable=False)
    op.create_unique_constraint(
        "uq_documento_contratual_projeto_tipo", "documento_contratual", ["projeto_id", "tipo"]
    )
    op.drop_column("documento_contratual", "cliente_externo")
    op.drop_column("documento_contratual", "nome_projeto_externo")
