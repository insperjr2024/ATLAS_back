"""diretoria_em_tres_cargos

Revision ID: a7c1e4b93f02
Revises: 3f2f5a4c9e1b
Create Date: 2026-08-20

Divide a diretoria em três cargos: `diretor_projetos` (o diretor de hoje, com
tudo), `diretor_pessoas` (visualização + Avaliação de Desempenho) e `diretor`,
que passa a significar só-visualização.

⭐ **Esta migration é INERTE de propósito.** Ela não promove ninguém e não
rebaixa ninguém:

- `usuario.posicao` não é tocada — quem é `diretor` continua `diretor`;
- a linha `diretor` de `posicao_permissao` fica como está, com tudo ligado.

O motivo é a ordem dos fatos. Os usuários só mudam de cargo no passo manual,
feito conta a conta depois do deploy (e fora do versionamento: gente entra e
sai da empresa, um e-mail cravado aqui envelhece mal). Se esta migration já
rebaixasse a linha `diretor`, todo mundo perderia Monitoramento, Desempenho e
Configurações no instante do `upgrade` — antes de existir um só
`diretor_projetos` para promover os outros. O rebaixamento é o ÚLTIMO passo da
virada, feito pela tela de Configurações, que existe exatamente para isso.

`usuario_posicao_historico` também não é reescrita: as linhas antigas dizem que
aquela pessoa FOI `diretor` no modelo antigo, e isso continua verdade. A
promoção gera linhas novas pelo caminho normal.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

from src.utils.alembic_pg import redefinir_enum_postgres

# revision identifiers, used by Alembic.
revision: str = 'a7c1e4b93f02'
down_revision: Union[str, Sequence[str], None] = '3f2f5a4c9e1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POSICOES_ANTES = ('diretor', 'gerente', 'coordenador', 'consultor')
POSICOES_DEPOIS = (
    'diretor_projetos',
    'diretor_pessoas',
    'diretor',
    'gerente',
    'coordenador',
    'consultor',
)

# tabela, coluna, nome do tipo — os três enums que listam posição.
ENUMS = (
    ('usuario', 'posicao', 'posicao_usuario'),
    ('posicao_permissao', 'posicao', 'posicao_permissao_posicao'),
    ('usuario_posicao_historico', 'posicao', 'posicao_historico'),
)

CAIXAS = (
    'pode_criar_projeto',
    'pode_editar_equipe',
    'pode_gerir_membros',
    'pode_marcar_kickoff',
    'pode_definir_cronograma',
    'pode_criar_tarefa',
    'pode_mover_editar_tarefa',
    'pode_ver_proprios_projetos',
    'pode_ver_monitoramento',
    'pode_administrar_desempenho',
    'pode_editar_formularios_desempenho',
    'pode_administrar_configuracoes',
    'pode_ver_todos_projetos',
)

# O diretor de projetos herda o diretor de hoje: tudo ligado.
DIRETOR_PROJETOS = {caixa: True for caixa in CAIXAS}

# Gestão de pessoas = o diretor comum + Avaliação de Desempenho. Vê todos os
# projetos e administra Membros, mas não conduz projeto, não abre Monitoramento
# e não mexe no Sistema.
DIRETOR_PESSOAS = {caixa: False for caixa in CAIXAS}
DIRETOR_PESSOAS.update(
    pode_gerir_membros=True,
    pode_ver_proprios_projetos=True,
    pode_ver_todos_projetos=True,
    pode_administrar_desempenho=True,
    pode_editar_formularios_desempenho=True,
)


def _redefinir(de, para) -> None:
    """Redefine os três enums de `de` para `para`.

    Os dois caminhos são excludentes, como nas outras migrations de enum desta
    base (ver `6172519c6fab`): no Postgres o ENUM é um TYPE à parte e o helper
    faz a troca inteira sozinho; no MySQL o conjunto vive na coluna e quem
    resolve é o `alter_column`.
    """
    postgres = op.get_bind().dialect.name == 'postgresql'
    for tabela, coluna, tipo in ENUMS:
        if postgres:
            redefinir_enum_postgres(op, tabela, coluna, tipo, list(para))
        else:
            op.alter_column(
                tabela,
                coluna,
                existing_type=mysql.ENUM(*de),
                type_=sa.Enum(*para, name=tipo),
                existing_nullable=False,
            )


def _tabela_posicao_permissao():
    return sa.table(
        'posicao_permissao',
        sa.column('posicao', sa.String),
        *[sa.column(caixa, sa.Boolean) for caixa in CAIXAS],
    )


def upgrade() -> None:
    _redefinir(POSICOES_ANTES, POSICOES_DEPOIS)

    # As duas linhas novas. A linha `diretor` que já existe NÃO é tocada —
    # ver a explicação no topo do arquivo.
    op.bulk_insert(
        _tabela_posicao_permissao(),
        [
            {'posicao': 'diretor_projetos', **DIRETOR_PROJETOS},
            {'posicao': 'diretor_pessoas', **DIRETOR_PESSOAS},
        ],
    )


def downgrade() -> None:
    # ⚠ A ORDEM importa, e `posicao_permissao` é o caso especial.
    #
    # Ela tem UNIQUE em `posicao`, e a linha `diretor` nunca deixou de existir
    # (o upgrade não a tocou). Converter `diretor_projetos` para `diretor` ali
    # colidiria com essa linha. Então nesta tabela as linhas novas são
    # APAGADAS, e só nas outras duas o valor é convertido de volta.
    op.execute(
        "DELETE FROM posicao_permissao "
        "WHERE posicao IN ('diretor_projetos', 'diretor_pessoas')"
    )

    # Ninguém pode sobrar num cargo que vai deixar de existir, senão a troca do
    # enum estoura com dado inválido. Quem foi promovido volta a ser `diretor`,
    # que é de onde saiu.
    for tabela, coluna, _ in ENUMS:
        if tabela == 'posicao_permissao':
            continue
        op.execute(
            f"UPDATE {tabela} SET {coluna} = 'diretor' "
            f"WHERE {coluna} IN ('diretor_projetos', 'diretor_pessoas')"
        )

    _redefinir(POSICOES_DEPOIS, POSICOES_ANTES)
