"""permissoes_cargo_tabela_do_briefing

Troca as 7 caixas antigas do cargo pelas 10 da tabela do §3.

As 7 antigas (agendar banca, formulário de banca, membros, núcleo, cargos e as
duas de desempenho) são REMOVIDAS. Só `pode_gerenciar_membros` tinha
equivalente entre as 10 (virou `pode_gerir_membros`); as outras 6 voltam a ser
travadas por posição direto na rota, como era antes de existirem caixas.

As 10 novas nascem com o padrão da tabela, aplicado por POSIÇÃO: cada cargo
recebe o padrão da posição das pessoas que o ocupam. O padrão é só o valor
inicial — daí em diante quem manda é a caixa, editável na tela de Cargos.

                                    Dir  Ger  Coord  Cons
  Criar projeto e alocar equipe      x    x     -     -
  Editar a equipe de um projeto      x    x     -     -
  Gerir membros (posição e status)   x    -     -     -
  Marcar kickoff e data de entrega   x    x     x     x
  Definir cronograma por escopo      x    x     x     -
  Aprovar reajuste de cronograma     x    -     -     -
  Criar tarefa                       x    x     x     x
  Mover e editar tarefa              x    x     x     x
  Ver os próprios projetos           x    x     x     x
  Monitoramento e alocação           x    x     -     -

Revision ID: 7514970fac39
Revises: 0aa4dd79044f
Create Date: 2026-08-05 15:39:17.768547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7514970fac39'
down_revision: Union[str, Sequence[str], None] = '0aa4dd79044f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# As 10 novas, na ordem da tabela.
NOVAS = [
    "pode_criar_projeto",
    "pode_editar_equipe",
    "pode_gerir_membros",
    "pode_marcar_kickoff",
    "pode_definir_cronograma",
    "pode_aprovar_reajuste",
    "pode_criar_tarefa",
    "pode_mover_editar_tarefa",
    "pode_ver_proprios_projetos",
    "pode_ver_monitoramento",
]

# As 7 que saem, com o tipo para o downgrade poder recriá-las.
ANTIGAS = [
    "pode_definir_formulario",
    "pode_agendar_banca",
    "pode_gerenciar_cargos",
    "pode_gerenciar_membros",
    "pode_gerenciar_nucleo",
    "pode_gerenciar_desempenho",
    "pode_definir_formulario_desempenho",
]

# O padrão de cada posição — a tabela do docstring, em código.
PADRAO_POR_POSICAO = {
    "diretor": NOVAS,  # a diretoria marca todas
    "gerente": [
        "pode_criar_projeto",
        "pode_editar_equipe",
        "pode_marcar_kickoff",
        "pode_definir_cronograma",
        "pode_criar_tarefa",
        "pode_mover_editar_tarefa",
        "pode_ver_proprios_projetos",
        "pode_ver_monitoramento",
    ],
    "coordenador": [
        "pode_marcar_kickoff",
        "pode_definir_cronograma",
        "pode_criar_tarefa",
        "pode_mover_editar_tarefa",
        "pode_ver_proprios_projetos",
    ],
    "consultor": [
        "pode_marcar_kickoff",
        "pode_criar_tarefa",
        "pode_mover_editar_tarefa",
        "pode_ver_proprios_projetos",
    ],
}


def upgrade() -> None:
    """Upgrade schema."""
    for coluna in NOVAS:
        op.add_column(
            "cargo",
            sa.Column(coluna, sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    # O padrão entra por posição. Cargo e posição são dimensões independentes,
    # então a ligação é feita pelas pessoas: o cargo recebe o padrão da posição
    # de quem o ocupa. Da posição mais fraca para a mais forte, para um cargo
    # ocupado por gente de posições diferentes acabar com o padrão da mais alta
    # — errar para o lado de não tirar acesso de ninguém.
    for posicao in ("consultor", "coordenador", "gerente", "diretor"):
        colunas = PADRAO_POR_POSICAO[posicao]
        atribuicoes = ", ".join(f"{c} = TRUE" for c in colunas)
        op.execute(
            f"""
            UPDATE cargo SET {atribuicoes}
             WHERE id IN (
                   SELECT cargo_id FROM (
                          SELECT DISTINCT cargo_id FROM usuario WHERE posicao = '{posicao}'
                   ) AS cargos_da_posicao
             )
            """
        )

    # O server_default já preencheu as linhas existentes; daqui em diante quem
    # define o valor é o model (default=False).
    for coluna in NOVAS:
        op.alter_column("cargo", coluna, server_default=None,
                        existing_type=sa.Boolean(), existing_nullable=False)

    for coluna in ANTIGAS:
        op.drop_column("cargo", coluna)


def downgrade() -> None:
    """Downgrade schema."""
    for coluna in ANTIGAS:
        op.add_column(
            "cargo",
            sa.Column(coluna, sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("cargo", coluna, server_default=None,
                        existing_type=sa.Boolean(), existing_nullable=False)

    for coluna in NOVAS:
        op.drop_column("cargo", coluna)
