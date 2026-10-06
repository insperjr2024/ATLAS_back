"""unifica heads: Health Track com a Avaliação do Escopo na periódica

As duas linhas saíram de `f1a9c47db235` em paralelo e entraram na main com
minutos de diferença (2026-10-05), deixando duas heads — o
`alembic upgrade head` do deploy recusa subir assim. Nenhuma das duas mexe
nas tabelas da outra, então esta revisão só junta as pontas.

Revision ID: d1b8f4a6e372
Revises: a9d4e7c2b185, c4f9a2e7d816
Create Date: 2026-10-05 23:15:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'd1b8f4a6e372'
down_revision: Union[str, Sequence[str], None] = ('a9d4e7c2b185', 'c4f9a2e7d816')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
