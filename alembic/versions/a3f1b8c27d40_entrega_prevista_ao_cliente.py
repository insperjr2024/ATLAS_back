"""entrega_prevista_ao_cliente

A PROMESSA feita ao cliente na venda, definida já na criação do projeto.

⚠ Coluna NOVA, e não reaproveitamento de `projeto.data_entrega_cliente`. São
duas perguntas diferentes: esta guarda o que foi PROMETIDO; aquela guardava o
que ACONTECEU e por isso foi aposentada — virou derivada da entrega do último
escopo. Juntar as duas no mesmo campo foi o bug original: a promessa era
sobrescrita pela realidade e ninguém mais sabia qual das duas estava vendo.

Nullable porque todo projeto que já existe não tem promessa registrada, e
inventar uma seria pior que deixar vazio.

Revision ID: a3f1b8c27d40
Revises: 082aef445ead
Create Date: 2026-08-12 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f1b8c27d40"
down_revision: Union[str, Sequence[str], None] = "082aef445ead"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projeto", sa.Column("data_entrega_prevista_cliente", sa.Date(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("projeto", "data_entrega_prevista_cliente")
