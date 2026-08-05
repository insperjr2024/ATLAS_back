"""permissoes_cargo_desempenho

Duas caixas novas no cargo para a Avaliação de Desempenho (P4):

- `pode_gerenciar_desempenho` — o painel inteiro: resultados (quem avaliou
  quem, avaliados, relatórios, pendências), lotes e mentorias;
- `pode_definir_formulario_desempenho` — editar os formulários.

Antes essas rotas eram travadas por `posicao` direto no router
(`require_gestao` e `require_diretor`). Como agora quem decide é só a caixa, o
backfill abaixo marca as caixas nos cargos de quem JÁ tinha acesso pela
posição — senão a diretoria perderia o painel no instante do deploy.

O backfill é por cargo-de-quem-tem-a-posição, e não por um nome fixo de cargo,
porque `cargo` e `posicao` são dimensões independentes: quem é gerente de
frente pode estar em qualquer cargo.

Revision ID: 0aa4dd79044f
Revises: d23f2cba6f5d
Create Date: 2026-08-05 13:19:41.783626

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0aa4dd79044f'
down_revision: Union[str, Sequence[str], None] = 'd23f2cba6f5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "cargo",
        sa.Column("pode_gerenciar_desempenho", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "cargo",
        sa.Column("pode_definir_formulario_desempenho", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Backfill: quem tinha acesso por posição continua tendo, agora pela caixa.
    # `require_gestao` era diretor + gerente.
    op.execute(
        """
        UPDATE cargo SET pode_gerenciar_desempenho = TRUE
         WHERE id IN (
               SELECT cargo_id FROM (
                      SELECT DISTINCT cargo_id FROM usuario
                       WHERE posicao IN ('diretor', 'gerente')
               ) AS cargos_com_gestao
         )
        """
    )
    # `require_diretor` era só a diretoria.
    op.execute(
        """
        UPDATE cargo SET pode_definir_formulario_desempenho = TRUE
         WHERE id IN (
               SELECT cargo_id FROM (
                      SELECT DISTINCT cargo_id FROM usuario
                       WHERE posicao = 'diretor'
               ) AS cargos_de_diretoria
         )
        """
    )

    # O server_default já cumpriu o papel de preencher as linhas existentes.
    # Daqui em diante quem define o valor é o model (default=False), como nas
    # outras caixas de permissão.
    op.alter_column("cargo", "pode_gerenciar_desempenho", server_default=None,
                    existing_type=sa.Boolean(), existing_nullable=False)
    op.alter_column("cargo", "pode_definir_formulario_desempenho", server_default=None,
                    existing_type=sa.Boolean(), existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("cargo", "pode_definir_formulario_desempenho")
    op.drop_column("cargo", "pode_gerenciar_desempenho")
