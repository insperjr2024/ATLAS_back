"""corrige_indice_token_aprovacao

Revision ID: f1a6c3e8b920
Revises: e7c4b8f2a319
Create Date: 2026-09-23 00:00:00.000000

⭐ 2026-09-23 — achado revisando a branch antes do merge (`alembic check`
contra os models): a migration original de Contratos (`343e1f0be526`)
criou `token` com um UNIQUE CONSTRAINT ("token_aprovacao_contratual_
token_key") E um índice comum separado ("ix_token_aprovacao_contratual_
token") — dois objetos, nenhum deles batendo com o model
(`TokenAprovacaoContratualModel.token = Column(..., unique=True,
index=True)`, que no SQLAlchemy é um único índice ÚNICO). Funciona hoje
(a coluna É única na prática, via a constraint) mas diverge do que o
model declara — corrige aqui, tirando a constraint redundante e tornando
o índice único, do jeito que o model sempre esperou.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1a6c3e8b920'
down_revision: Union[str, Sequence[str], None] = 'e7c4b8f2a319'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "token_aprovacao_contratual_token_key", "token_aprovacao_contratual", type_="unique"
    )
    op.drop_index("ix_token_aprovacao_contratual_token", table_name="token_aprovacao_contratual")
    op.create_index(
        "ix_token_aprovacao_contratual_token",
        "token_aprovacao_contratual",
        ["token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_token_aprovacao_contratual_token", table_name="token_aprovacao_contratual")
    op.create_index(
        "ix_token_aprovacao_contratual_token",
        "token_aprovacao_contratual",
        ["token"],
        unique=False,
    )
    op.create_unique_constraint(
        "token_aprovacao_contratual_token_key", "token_aprovacao_contratual", ["token"]
    )
