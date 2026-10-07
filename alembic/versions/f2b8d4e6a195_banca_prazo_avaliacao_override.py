"""banca.prazo_avaliacao_override: abrir/fechar avaliação na mão

Revision ID: f2b8d4e6a195
Revises: e5a1c7d9b304
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2b8d4e6a195"
down_revision: Union[str, Sequence[str], None] = "e5a1c7d9b304"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIPO = sa.Enum("aberto", "fechado", name="banca_prazo_avaliacao_override")


def upgrade() -> None:
    # `add_column` não cria o tipo do enum no Postgres; sem isto a coluna
    # não entra e toda consulta em `banca` quebra.
    TIPO.create(op.get_bind(), checkfirst=True)
    op.add_column("banca", sa.Column("prazo_avaliacao_override", TIPO, nullable=True))


def downgrade() -> None:
    op.drop_column("banca", "prazo_avaliacao_override")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS banca_prazo_avaliacao_override")
