"""ordem_do_escopo_vendido

Revision ID: 9ef5e8c8a983
Revises: 3a55df5fef52
Create Date: 2026-08-07 00:44:36.290481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ef5e8c8a983'
down_revision: Union[str, Sequence[str], None] = '3a55df5fef52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ORDEM_PADRAO_BUSINESS = {
    "Análise Mercadológica": 0,
    "Plano Operacional": 1,
    "Plano Estratégico de Marketing": 2,
    "Viabilidade Financeira": 3,
}


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "projeto_escopo", sa.Column("ordem", sa.Integer(), nullable=False, server_default="0")
    )

    # Backfill: quem já tinha os 4 escopos clássicos da Business ganha a
    # hierarquia certa retroativamente, sem precisar reordenar cada projeto
    # existente na mão. Subquery em vez de `UPDATE ... JOIN` (exclusivo do
    # MySQL) — roda igual em MySQL e Postgres.
    conexao = op.get_bind()
    for nome, ordem in ORDEM_PADRAO_BUSINESS.items():
        conexao.execute(
            sa.text(
                "UPDATE projeto_escopo SET ordem = :ordem "
                "WHERE escopo_id IN (SELECT id FROM escopo WHERE nome = :nome)"
            ),
            {"ordem": ordem, "nome": nome},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("projeto_escopo", "ordem")
