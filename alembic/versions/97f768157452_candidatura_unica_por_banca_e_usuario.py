"""candidatura única por banca e usuário

Revision ID: 97f768157452
Revises: bb255f970798
Create Date: 2026-09-16

Nada no `CreateCandidaturaUseCase` impedia a mesma pessoa virar candidata
duas vezes da mesma banca — um duplo-clique em "Alocar-se", ou a gestão
adicionando quem já estava lá, criava outra linha igual sem erro nenhum.
Foi assim que uma consultora apareceu 4x na ficha do GELATTO, e alguém
teve que apagar as duplicatas à mão.

Conferido antes de escrever esta migration: nenhum par (banca_id,
usuario_id) duplicado em produção hoje, então a constraint entra sem
precisar de limpeza.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97f768157452"
down_revision: Union[str, Sequence[str], None] = "bb255f970798"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_candidatura_banca_usuario",
        "candidatura",
        ["banca_id", "usuario_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_candidatura_banca_usuario", "candidatura", type_="unique")
