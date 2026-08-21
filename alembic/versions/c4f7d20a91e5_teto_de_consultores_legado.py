"""teto_de_consultores_legado

Revision ID: c4f7d20a91e5
Revises: b8e3f1a56c04
Create Date: 2026-08-21

Sobe o `max_consultores` dos projetos que já estouraram o próprio teto.

**Não é bug de lógica.** As três vias de entrada de consultor validam o teto:
`validacao_equipe.py` (criação e edição de equipe) e as duas de
`solicitacao_projeto.py` (aprovar pedido e alocar direto). Baixar o teto
também valida contra a equipe atual (`update_configuracoes.py`).

**É dado legado.** A migration `00b38e9fa008` (2026-08-07) acrescentou a
coluna assim:

    op.add_column('projeto', sa.Column('max_consultores', sa.Integer(),
                  server_default='3', nullable=False))

Todo projeto que já existia ficou com teto 3, tivesse quantos consultores
tivesse. O Atlas Tech, com 5, passou a se descrever como "5 de 3" na tela de
Vagas — e o indicador de pontinhos, que desenha `max_consultores` bolinhas,
mostrava 3 para 5 pessoas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4f7d20a91e5'
down_revision: Union[str, Sequence[str], None] = 'b8e3f1a56c04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conexao = op.get_bind()

    # Consultores ATIVOS por projeto (`saiu_em IS NULL`): o teto é sobre quem
    # está no time hoje, não sobre quem já passou por ele.
    consultores = conexao.execute(
        sa.text(
            "SELECT projeto_id, COUNT(*) AS n FROM projeto_membro "
            " WHERE papel = 'consultor' AND saiu_em IS NULL "
            " GROUP BY projeto_id"
        )
    ).fetchall()

    # Laço em Python, e não um `UPDATE ... FROM` só: a sintaxe de
    # update-com-join difere entre Postgres e MySQL, e esta base roda os dois
    # (ver `utils/alembic_pg.py`). São dezenas de projetos, não milhares.
    for projeto_id, quantos in consultores:
        # ⭐ Só SOBE, nunca desce. Um projeto com teto 8 e 2 consultores
        # continua com 8: o teto é a decisão de quem monta o time sobre quantos
        # ainda cabem, não o retrato de quantos entraram até agora. Rebaixá-lo
        # aqui fecharia vagas que alguém abriu de propósito.
        conexao.execute(
            sa.text(
                "UPDATE projeto SET max_consultores = :n "
                " WHERE id = :id AND max_consultores < :n"
            ),
            {"n": quantos, "id": projeto_id},
        )


def downgrade() -> None:
    """Não há o que desfazer, e isto é deliberado.

    O valor anterior era 3 para todo mundo — o `server_default` da migration
    que criou a coluna, não uma escolha de ninguém. Restaurá-lo colocaria de
    volta exatamente o defeito que este upgrade corrigiu, e ainda por cima em
    projetos cujo teto pode ter sido ajustado à mão depois.
    """
