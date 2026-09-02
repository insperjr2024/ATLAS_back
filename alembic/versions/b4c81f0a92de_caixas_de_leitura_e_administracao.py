"""caixas_de_leitura_e_administracao

Revision ID: b4c81f0a92de
Revises: a893953b013c
Create Date: 2026-09-02

Da 15ª à 21ª caixa de `posicao_permissao`.

Todas nasceram do mesmo levantamento: áreas que continuavam presas a POSIÇÃO
enquanto as vizinhas de tela já eram caixa. Cinco são delegação nova; duas
partem uma caixa existente que fazia trabalhos de riscos diferentes.

Delegação nova:

- `pode_ver_historico_projetos` — a aba Histórico do Monitoramento. Era
  `require_gestao` (posição), a única aba do painel fora de uma caixa.
- `pode_ver_tarefas_gerais` e `pode_ver_cronogramas_gerais` — os dois boards
  macro. Eram `require_diretor_projetos`, as outras duas exceções do painel.
- `pode_configurar_colunas` — as colunas do kanban. Criar e mover tarefa já
  eram caixa; só o redesenho da coluna seguia preso à posição.
- `pode_aprovar_pedidos` — responder a fila de Aprovações (dias de ajuste,
  exceção de choque, banca fora da janela).

Divisão de `pode_administrar_configuracoes`, que fazia TRÊS trabalhos:

- `pode_administrar_permissoes` — editar esta própria tabela. É de outra
  ordem de risco: decide quem pode o quê na plataforma inteira.
- `pode_gerir_calendarios_base` — dias não letivos, importação do PDF e nome
  dos calendários.
- a caixa antiga fica com o catálogo (escopos, frentes, combinações) e o
  cadastro de semestre.

⭐ **A migration não muda o acesso de ninguém.** Cada coluna nasce `false` e é
ligada exatamente em quem já passava pelo guard antigo:

- as cinco novas, em quem satisfazia `require_diretor_projetos` — mais o
  gerente no histórico, que satisfazia `require_gestao`;
- as duas da divisão, em quem já tinha `pode_administrar_configuracoes`
  marcada AGORA (e não numa lista fixa: a caixa é editável em Configurações,
  então o valor de hoje é a única fonte correta).

Quem quiser delegar liga a caixa em Configurações depois — que é o ponto de
elas existirem.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b4c81f0a92de'
down_revision: Union[str, Sequence[str], None] = 'a893953b013c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: As cinco de delegação nova, com quem já passava pelo guard antigo.
#: O histórico é o único com gerente: era `require_gestao`, não
#: `require_diretor_projetos`.
NOVAS = {
    'pode_ver_historico_projetos': ('diretor_projetos', 'gerente'),
    'pode_ver_tarefas_gerais': ('diretor_projetos',),
    'pode_ver_cronogramas_gerais': ('diretor_projetos',),
    'pode_configurar_colunas': ('diretor_projetos',),
    'pode_aprovar_pedidos': ('diretor_projetos',),
}

#: As duas que saíram de `pode_administrar_configuracoes` e herdam o valor
#: dela linha a linha.
HERDAM_DE_CONFIGURACOES = (
    'pode_administrar_permissoes',
    'pode_gerir_calendarios_base',
)

TODAS = tuple(NOVAS) + HERDAM_DE_CONFIGURACOES


def _tabela(*colunas: str):
    return sa.table(
        'posicao_permissao',
        sa.column('posicao', sa.String),
        sa.column('pode_administrar_configuracoes', sa.Boolean),
        *(sa.column(nome, sa.Boolean) for nome in colunas),
    )


def upgrade() -> None:
    for coluna in TODAS:
        op.add_column(
            'posicao_permissao',
            sa.Column(coluna, sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    tabela = _tabela(*TODAS)

    for coluna, posicoes in NOVAS.items():
        op.execute(
            tabela.update()
            .where(tabela.c.posicao.in_(posicoes))
            .values(**{coluna: True})
        )

    # Copia o valor ATUAL da caixa que está sendo partida — em vez de uma
    # lista de posições escrita à mão. Ela é editável em Configurações, então
    # quem a tem hoje pode não ser quem a tinha quando ela nasceu, e é o
    # estado de hoje que precisa sobreviver à divisão.
    for coluna in HERDAM_DE_CONFIGURACOES:
        op.execute(
            tabela.update()
            .where(tabela.c.pode_administrar_configuracoes.is_(True))
            .values(**{coluna: True})
        )


def downgrade() -> None:
    for coluna in reversed(TODAS):
        op.drop_column('posicao_permissao', coluna)
