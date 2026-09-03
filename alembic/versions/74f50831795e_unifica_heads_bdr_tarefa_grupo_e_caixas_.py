"""unifica heads: bdr, tarefa grupo e caixas de leitura

Ponto de encontro, sem DDL nenhum. Tres PRs entraram na `main` no mesmo dia,
cada um com uma migration filha de `a893953b013c`, e a `main` ficou com tres
cabecas: `alembic upgrade head` (e o deploy do Railway, que roda isso no
start) passou a falhar com "Multiple head revisions are present".

As tres cabecas:

- `b4c81f0a92de` - da 15a a 21a caixa de `posicao_permissao` (leitura e
  administracao);
- `405554f05dde` - `tarefa.grupo_id`, do "cada um faz a sua parte";
- `7f472ea3f8eb` - `usuario.bdr`, o consultor que tambem vende.

As tres tocam tabelas/colunas diferentes, entao a conciliacao e so este
merge: quem cria schema sao as revisions acima.

Revision ID: 74f50831795e
Revises: 405554f05dde, 7f472ea3f8eb, b4c81f0a92de
Create Date: 2026-09-02

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "74f50831795e"
down_revision: Union[str, Sequence[str], None] = (
    "405554f05dde",
    "7f472ea3f8eb",
    "b4c81f0a92de",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge puro: o schema vem das tres revisions acima.
    pass


def downgrade() -> None:
    # Desfazer um merge e voltar a ter tres cabecas - nada a executar aqui.
    pass
