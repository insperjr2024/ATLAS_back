"""unifica_heads_pdi_e_senha_provisoria

Ponto de encontro, sem DDL nenhum. Três cabeças chegaram aqui:

- `21adfe0d3a5c` — desempenho/PDI, item e envio por item;
- `26b5ab871976` — a unificação anterior (situação, carga e reunião por escopo);
- `e3b1f7a9c204` — `usuario.senha_provisoria`, do primeiro acesso por e-mail.

As duas primeiras já vinham separadas na `main`: `alembic upgrade head` falhava
lá com "Multiple head revisions are present" antes desta branch existir. Como o
merge da `main` traz as duas para cá, a conciliação acontece neste arquivo —
não dá para subir o banco desta branch sem ela.

Revision ID: f4a2c8e01b93
Revises: 21adfe0d3a5c, 26b5ab871976, e3b1f7a9c204
Create Date: 2026-08-06 17:40:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'f4a2c8e01b93'
down_revision: Union[str, Sequence[str], None] = (
    '21adfe0d3a5c',
    '26b5ab871976',
    'e3b1f7a9c204',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Merge puro: quem cria tabela ou coluna são as três revisions acima.


def downgrade() -> None:
    """Downgrade schema."""
    # Desfazer um merge é voltar a ter três cabeças — nada a executar aqui.
