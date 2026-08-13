"""unifica a reforma de bancas com o pdi e o enum de notificacao

⚠ **Migration de MERGE — não cria nem altera nada.** Existe só para reunir as
duas cadeias que nasceram em paralelo a partir de `082aef445ead`:

- `272d44505958` — a reforma de bancas (sessões, voto, exceção de choque)
- `a71c4e93b8d2` — o PDI no banco e o enum de notificação no Postgres

Sem ela o Alembic fica com DUAS heads e `alembic upgrade head` falha com
"Multiple head revisions are present" — para todo mundo, não só para quem
mexeu em bancas. É o mesmo remédio que o repo já aplicou em `9ed5501ab9b8`,
`01f8f776e083` e `082aef445ead`.

`upgrade`/`downgrade` vazios de propósito: o schema já é produzido pelas duas
cadeias; aqui só o grafo é costurado.

Revision ID: 925c8d1287b1
Revises: 272d44505958, a71c4e93b8d2
Create Date: 2026-08-13 11:09:41.039392

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '925c8d1287b1'
down_revision: Union[str, Sequence[str], None] = ('272d44505958', 'a71c4e93b8d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
