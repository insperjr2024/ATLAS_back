"""teto de vagas por combinacao de frentes

Revision ID: d1f4a7c88b52
Revises: c3d7f9a21b40
Create Date: 2026-09-02

O TETO de quantas pessoas cabem numa banca passa a poder ser próprio da
COMBINAÇÃO de frentes, como já eram os mínimos e os máximos por frente.

Até aqui ele era um número só para a plataforma inteira
(`configuracao.vagas_por_banca`): a banca de Direito sozinha e a de
Business + Tech + Processos cabiam o mesmo tanto de gente, mesmo exigindo
mínimos bem diferentes.

⚠ **Nullable, e nada é preenchido.** `NULL` quer dizer "usa o global", que é o
comportamento de hoje — nenhuma banca marcada muda de teto por causa desta
migration. `configuracao.vagas_por_banca` continua existindo e continua sendo
o padrão de quem não configurou e da banca legada, que não tem frente
vinculada e por isso não cai em combinação nenhuma.

📐 **A coluna vive na tabela por (combinação, frente), repetida em todas as
linhas da combinação.** O teto é da combinação, não da frente — o normal seria
uma tabela só para ele. Mas a combinação é gravada como um BLOCO
(`BancaComposicaoRegraRepository.definir` apaga e recria todas as linhas de uma
vez), então as cópias não têm como divergir, e uma tabela nova custaria uma
junção em todo caminho que hoje é um `WHERE combinacao = ?`.
"""

import sqlalchemy as sa
from alembic import op

revision = "d1f4a7c88b52"
down_revision = "c3d7f9a21b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "banca_composicao_regra",
        sa.Column("vagas", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("banca_composicao_regra", "vagas")
