"""desempenho_lote.inclui_avaliacao_de_escopo

⭐ 2026-09-10, a pedido: ao abrir um lote de finalização À MÃO, a diretoria
escolhe se a Avaliação do Escopo (auto-avaliação sobre o formulário
`(finalizacao, escopo)`) entra junto ou não. Antes ela entrava sempre que o
formulário tinha conteúdo.

`DEFAULT true`: lotes já existentes e a finalização automática
(`FinalizacaoAutomaticaBancaUseCase`, que não passa o campo) continuam
incluindo. Periódica ignora — a Avaliação do Escopo só existe na finalização.

Revision ID: a3f8c1e29b47
Revises: b5f1e0d9c473
Create Date: 2026-09-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f8c1e29b47"
down_revision: Union[str, None] = "b5f1e0d9c473"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "desempenho_lote",
        sa.Column(
            "inclui_avaliacao_de_escopo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("desempenho_lote", "inclui_avaliacao_de_escopo")
