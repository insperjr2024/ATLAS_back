"""notificacao_remarcacao_e_lote

Revision ID: d81e5a2c9f37
Revises: c3f70b18d942
Create Date: 2026-08-06 12:40:00.000000

Três tipos novos no ENUM de `notificacao.tipo`:

- `banca_remarcada` e `entrega_alterada` — o §5.6 exige que remarcar não seja
  silencioso, e mudar a data prometida ao cliente tem o mesmo peso: quem
  planejou em cima dela precisa saber.
- `lote_desempenho_aberto` — abrir um lote de Avaliação de Desempenho é o
  momento em que as avaliações passam a existir para quem responde.

Só o ENUM muda; nenhuma coluna nova. Em MySQL, ampliar um ENUM é um
`MODIFY COLUMN` com a lista completa — os valores antigos continuam válidos e
nenhuma linha existente é tocada.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd81e5a2c9f37'
down_revision: Union[str, Sequence[str], None] = 'c3f70b18d942'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ANTES = (
    'alocado_em_projeto',
    'entrega_registrada',
    'escalacao_banca',
    'troca_banca',
    'avaliacao_pendente',
    'banca_aviso',
    'kickoff_pendente',
    'tarefa_vencida',
    'banca_nao_marcada',
    'projeto_sem_reuniao',
    'banca_hoje',
)

DEPOIS = ANTES + ('banca_remarcada', 'entrega_alterada', 'lote_desempenho_aberto')


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'notificacao', 'tipo',
        existing_type=sa.Enum(*ANTES, name='tipo_notificacao'),
        type_=sa.Enum(*DEPOIS, name='tipo_notificacao'),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # As linhas dos tipos que estão saindo precisam sumir antes: o MySQL
    # aceitaria o MODIFY e converteria cada valor inválido em string vazia,
    # deixando notificação órfã e sem tipo em vez de falhar.
    op.execute(
        "DELETE FROM notificacao WHERE tipo IN "
        "('banca_remarcada', 'entrega_alterada', 'lote_desempenho_aberto')"
    )
    op.alter_column(
        'notificacao', 'tipo',
        existing_type=sa.Enum(*DEPOIS, name='tipo_notificacao'),
        type_=sa.Enum(*ANTES, name='tipo_notificacao'),
        existing_nullable=False,
    )
