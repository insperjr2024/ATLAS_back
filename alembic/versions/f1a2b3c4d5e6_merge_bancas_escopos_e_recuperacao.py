"""merge_bancas_escopos_e_recuperacao

Revision ID: f1a2b3c4d5e6
Revises: c41a7b90e5d2, a9267ae28eeb
Create Date: 2026-08-05 18:10:00.000000

Dois heads abertos ao mesmo tempo: `c41a7b90e5d2` (banca cobre vários escopos)
e `a9267ae28eeb` (token de recuperação de senha) saíram de PRs paralelos e
nenhum dos dois desceu do outro. Com dois heads, `alembic upgrade head` falha —
qualquer migration nova precisa deste merge antes.

Vazia de propósito: não muda schema nenhum, só junta as duas pontas. Mesmo
padrão de `d23f2cba6f5d_merge_permissoes_cargo_e_desempenho.py`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = ('c41a7b90e5d2', 'a9267ae28eeb')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
