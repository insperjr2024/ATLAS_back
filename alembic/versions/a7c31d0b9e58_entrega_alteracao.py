"""entrega_alteracao

O registro das mudanças de data de entrega (§13).

Marcar a entrega continua livre — é o passo normal do fluxo, feito no próprio
cronograma. O que passa a exigir a diretoria é **alterar** uma entrega já
registrada: a data que o cliente ouviu é a promessa do projeto, e trocá-la em
silêncio apagaria a diferença entre "entregamos no prazo" e "mudamos o prazo".

Irmã de `banca_remarcacao`, criada na migration anterior e pelo mesmo motivo: a
coluna de origem (`projeto_escopo.data_entrega_real` ou
`projeto.data_entrega_cliente`) guarda só a data que vale agora, e sem esta
tabela o "de 15/09 para 22/09" existiria apenas na notificação já lida — a aba
Histórico não teria de onde reconstruir a decisão.

`projeto_escopo_id` nulo = entrega do projeto ao cliente; preenchido = entrega
daquele escopo.

Revision ID: a7c31d0b9e58
Revises: e93cec587f4a
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7c31d0b9e58'
down_revision: Union[str, Sequence[str], None] = 'e93cec587f4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'entrega_alteracao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('projeto_id', sa.Integer(), nullable=False),
        sa.Column('projeto_escopo_id', sa.Integer(), nullable=True),
        sa.Column('data_anterior', sa.Date(), nullable=True),
        sa.Column('data_nova', sa.Date(), nullable=False),
        sa.Column('justificativa', sa.String(length=500), nullable=False),
        sa.Column('alterado_por', sa.Integer(), nullable=False),
        sa.Column('autorizado_por', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['alterado_por'], ['usuario.id'], ),
        sa.ForeignKeyConstraint(['autorizado_por'], ['usuario.id'], ),
        sa.ForeignKeyConstraint(['projeto_escopo_id'], ['projeto_escopo.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['projeto_id'], ['projeto.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_entrega_alteracao_id'), 'entrega_alteracao', ['id'], unique=False)
    op.create_index(
        op.f('ix_entrega_alteracao_projeto_id'), 'entrega_alteracao', ['projeto_id'], unique=False
    )
    op.create_index(
        op.f('ix_entrega_alteracao_projeto_escopo_id'),
        'entrega_alteracao',
        ['projeto_escopo_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema.

    ⚠ Derruba o histórico de alterações de entrega junto — ele não tem outra
    fonte. O gate em si volta a não existir, então nada fica inconsistente.

    ⚠ Só o `drop_table`, sem `drop_index` antes: no MySQL os índices de
    `projeto_id` e `projeto_escopo_id` sustentam as chaves estrangeiras, e
    tentar apagá-los primeiro falha com "needed in a foreign key constraint".
    Derrubar a tabela leva índices e FKs junto.
    """
    op.drop_table('entrega_alteracao')
