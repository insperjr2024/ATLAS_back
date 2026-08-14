"""confirmacao_da_entrega_do_escopo

⭐ Separa GRAVAR A DATA de CONFIRMAR A ENTREGA (§5.5).

Antes, `data_entrega_real` e `status="entregue"` eram escritos na mesma linha:
marcar a data no cronograma já mudava a tabela de escopos para "Entregue". Um
clique num calendário passava por declaração de que o trabalho foi ao cliente.

Agora o status só muda pela confirmação explícita do coordenador do projeto ou
da diretoria, e estas colunas guardam quem confirmou e quando.

⚠ **Backfill obrigatório.** Sem ele, todo escopo já entregue apareceria como
"aguardando confirmação" — a tela pediria de novo um ato que já aconteceu, em
cima de dado histórico. `entrega_confirmada_em` recebe a própria data de
entrega, que é a melhor aproximação disponível: é quando o escopo de fato foi
ao cliente. `entrega_confirmada_por` fica NULO de propósito — ninguém confirmou
aqueles, e inventar um autor seria pior que admitir a lacuna.

Revision ID: bb6fdb2cd834
Revises: e4b1d7c9a052
Create Date: 2026-08-13 15:03:25.906989

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb6fdb2cd834'
down_revision: Union[str, Sequence[str], None] = 'e4b1d7c9a052'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("projeto_escopo", sa.Column("entrega_confirmada_em", sa.DateTime(), nullable=True))
    op.add_column(
        "projeto_escopo", sa.Column("entrega_confirmada_por", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_projeto_escopo_entrega_confirmada_por",
        "projeto_escopo",
        "usuario",
        ["entrega_confirmada_por"],
        ["id"],
    )

    # O backfill: o que já está entregue já foi confirmado por definição.
    op.execute(
        """
        UPDATE projeto_escopo
           SET entrega_confirmada_em = data_entrega_real
         WHERE status = 'entregue' AND data_entrega_real IS NOT NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_projeto_escopo_entrega_confirmada_por", "projeto_escopo", type_="foreignkey"
    )
    op.drop_column("projeto_escopo", "entrega_confirmada_por")
    op.drop_column("projeto_escopo", "entrega_confirmada_em")
