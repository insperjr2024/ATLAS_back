"""cargos dinâmicos

Revision ID: a9cae5c30c6d
Revises: e2b9d4a1f7c3
Create Date: 2026-09-16

`posicao` deixa de ser um ENUM fechado (6 valores fixos, iguais nas três
tabelas `usuario`, `posicao_permissao` e `usuario_posicao_historico`) e passa
a ser `VARCHAR`, com `posicao_permissao` como o catálogo — a mesma relação que
`frente`/`escopo` já tinham com quem os referencia, só que agora por FK de
string em vez de FK de `id`.

`posicao_permissao` ganha duas colunas:
- `nome`: o rótulo mostrado na tela (ex. "Diretor(a) de Projetos"). Até aqui
  esse rótulo vivia só no front (`ROTULO_POSICAO`, hardcoded); um cargo criado
  pela diretoria não está nesse dicionário, então precisa vir do banco.
- `e_padrao`: marca os 6 cargos que a plataforma sempre teve. Eles não podem
  ser apagados pela tela — dezenas de regras de negócio (`DIRETORIA`,
  `POSICOES_ELEGIVEIS_MENTOR`, `require_lideranca` etc., ver
  `middlewares/authorization.py`) continuam hardcoded a esses 6 valores
  específicos, e apagar um deles por baixo quebraria todas elas sem aviso.

⭐ **Um cargo novo (criado pela tela) nasce só com as caixas de
`posicao_permissao` marcadas na criação.** Ele NÃO entra em nenhuma das
listas de identidade hardcoded (não é elegível a mentor, não conta na
composição de banca, não enxerga o portfólio inteiro) — isso é escopo
deliberadamente de fora desta migration, o comportamento correto e já
existente para "ninguém, é um valor que essas tuplas não conhecem" continua
valendo. Ver a decisão registrada na conversa que pediu esta feature.

Adiciona uma FK `usuario.posicao -> posicao_permissao.posicao`: é o que passa
a impedir apagar um cargo que ainda tem gente nele (mesmo efeito de
`ResourceInUseError` que `frente`/`escopo` já têm, por FK de verdade em vez de
checagem manual). `usuario_posicao_historico` fica de fora da FK de propósito:
é um registro histórico ("a pessoa FOI isto"), e não pode travar a exclusão
de um cargo que ninguém mais ocupa só porque alguém já ocupou um dia.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "a9cae5c30c6d"
down_revision: Union[str, Sequence[str], None] = "e2b9d4a1f7c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POSICOES = ("diretor_projetos", "diretor_pessoas", "diretor", "gerente", "coordenador", "consultor")

ROTULOS = {
    "diretor_projetos": "Diretor(a) de Projetos",
    "diretor_pessoas": "Diretor(a) de Gestão de Pessoas",
    "diretor": "Diretor(a)",
    "gerente": "Gerente de frente",
    "coordenador": "Coordenador(a)",
    "consultor": "Consultor(a)",
}

# tabela, coluna, nome do tipo ENUM, tem default?
ENUMS = (
    ("usuario", "posicao", "posicao_usuario", True),
    ("posicao_permissao", "posicao", "posicao_permissao_posicao", False),
    ("usuario_posicao_historico", "posicao", "posicao_historico", False),
)

FK_USUARIO_POSICAO = "fk_usuario_posicao_posicao_permissao"


def _enum_para_varchar_pg(tabela: str, coluna: str, tem_default: bool, tamanho: int = 50) -> None:
    bind = op.get_bind()
    default = None
    if tem_default:
        default = bind.execute(
            sa.text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_name = :tabela AND column_name = :coluna"
            ),
            {"tabela": tabela, "coluna": coluna},
        ).scalar()
        if default:
            op.execute(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} DROP DEFAULT")

    op.execute(
        f"ALTER TABLE {tabela} ALTER COLUMN {coluna} TYPE VARCHAR({tamanho}) USING {coluna}::text"
    )

    if default:
        literal = default.split("::")[0]
        op.execute(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} SET DEFAULT {literal}")


def _varchar_para_enum_pg(tabela: str, coluna: str, tipo: str, valores, tem_default: bool) -> None:
    bind = op.get_bind()
    sa.Enum(*valores, name=tipo).create(bind, checkfirst=True)

    default = None
    if tem_default:
        default = bind.execute(
            sa.text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_name = :tabela AND column_name = :coluna"
            ),
            {"tabela": tabela, "coluna": coluna},
        ).scalar()
        if default:
            op.execute(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} DROP DEFAULT")

    op.execute(
        f"ALTER TABLE {tabela} ALTER COLUMN {coluna} TYPE {tipo} USING {coluna}::text::{tipo}"
    )

    if default:
        literal = default.split("::")[0]
        op.execute(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} SET DEFAULT {literal}")


def upgrade() -> None:
    postgres = op.get_bind().dialect.name == "postgresql"

    # 1. catálogo: rótulo + marca de cargo padrão (não apagável pela tela).
    op.add_column("posicao_permissao", sa.Column("nome", sa.String(length=100), nullable=True))
    op.add_column(
        "posicao_permissao",
        sa.Column("e_padrao", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    tabela_pp = sa.table(
        "posicao_permissao", sa.column("posicao", sa.String), sa.column("nome", sa.String)
    )
    for posicao, rotulo in ROTULOS.items():
        op.execute(
            tabela_pp.update().where(tabela_pp.c.posicao == posicao).values(nome=rotulo)
        )
    op.execute("UPDATE posicao_permissao SET e_padrao = true")
    op.alter_column("posicao_permissao", "nome", nullable=False)

    # 2. ENUM fechado -> VARCHAR nas três tabelas.
    for tabela, coluna, tipo, tem_default in ENUMS:
        if postgres:
            _enum_para_varchar_pg(tabela, coluna, tem_default)
        else:
            existing_default = "consultor" if tem_default else None
            op.alter_column(
                tabela,
                coluna,
                existing_type=mysql.ENUM(*POSICOES),
                type_=sa.String(length=50),
                existing_nullable=False,
                existing_server_default=existing_default,
            )

    if postgres:
        for _tabela, _coluna, tipo, _tem_default in ENUMS:
            op.execute(f"DROP TYPE {tipo}")

    # 3. o catálogo passa a ser a fonte da verdade: apagar um cargo com gente
    # nele recusa por FK, igual frente/escopo — sem checagem manual.
    op.create_foreign_key(
        FK_USUARIO_POSICAO,
        "usuario",
        "posicao_permissao",
        ["posicao"],
        ["posicao"],
    )


def downgrade() -> None:
    # ⚠ Downgrade assume que só os 6 cargos padrão existem. Se algum cargo
    # criado pela tela ainda existir, o cast de volta para ENUM falha — é
    # esperado: apague os cargos extras (e realoque quem estiver neles) antes
    # de descer esta migration.
    postgres = op.get_bind().dialect.name == "postgresql"

    op.drop_constraint(FK_USUARIO_POSICAO, "usuario", type_="foreignkey")

    for tabela, coluna, tipo, tem_default in ENUMS:
        if postgres:
            _varchar_para_enum_pg(tabela, coluna, tipo, POSICOES, tem_default)
        else:
            existing_default = "consultor" if tem_default else None
            op.alter_column(
                tabela,
                coluna,
                existing_type=sa.String(length=50),
                type_=mysql.ENUM(*POSICOES),
                existing_nullable=False,
                existing_server_default=existing_default,
            )

    op.drop_column("posicao_permissao", "e_padrao")
    op.drop_column("posicao_permissao", "nome")
