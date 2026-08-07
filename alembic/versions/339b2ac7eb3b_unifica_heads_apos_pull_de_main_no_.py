"""unifica heads apos pull de main no ajustes

Só junta os dois ramos, sem DDL — e é por isso que existe.

`b1c4d7e90a22` (a reconciliação do reajuste, desta branch) e `deda213224f9`
(o `criado_por` anulável, que veio da main no PR #50) nasceram em paralelo e
não se tocam: uma mexe em `cronograma_reajuste_solicitacao` e no enum de
notificação, a outra afrouxa três FKs de usuário. Sem este nó o
`alembic upgrade head` recusa com "múltiplas heads" mesmo não havendo
conflito nenhum entre elas.

Revision ID: 339b2ac7eb3b
Revises: b1c4d7e90a22, deda213224f9
Create Date: 2026-08-07 03:06:20.199776

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '339b2ac7eb3b'
down_revision: Union[str, Sequence[str], None] = ('b1c4d7e90a22', 'deda213224f9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
