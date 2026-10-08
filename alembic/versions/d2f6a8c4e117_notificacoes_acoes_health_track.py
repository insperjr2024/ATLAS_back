"""notificações das ações do Health Track

Revision ID: d2f6a8c4e117
Revises: c8e4a6b2f095
Create Date: 2026-10-08

Três tipos novos em `tipo_notificacao`: ação atribuída (pro responsável),
ação concluída (pra quem abriu) e prazo da ação vencido (responsável e
diretoria de projetos). `ALTER TYPE ... ADD VALUE` não roda dentro do bloco
transacional, por isso o `autocommit_block`.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d2f6a8c4e117"
down_revision: Union[str, Sequence[str], None] = "c8e4a6b2f095"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIPOS = ("acao_atribuida", "acao_concluida", "acao_prazo_vencido")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        for tipo in TIPOS:
            op.execute(f"ALTER TYPE tipo_notificacao ADD VALUE IF NOT EXISTS '{tipo}'")


def downgrade() -> None:
    """Sem volta: Postgres não remove valor de enum sem recriar o tipo."""
    pass
