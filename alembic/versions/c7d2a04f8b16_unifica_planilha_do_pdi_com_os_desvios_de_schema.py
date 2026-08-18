"""unifica a planilha do PDI com os desvios de schema

Dois trabalhos sairam do mesmo pai (`14390b63b8c6`) no mesmo dia e voltaram
por PRs diferentes:

- `7f4b0183bfc7` — planilha no enum de tipo_arquivo do item de PDI;
- `b3f9c17e4a28` — os tres desvios entre o schema do Postgres e os models.

Nenhum dos dois sabia do outro, e a main ficou com dois heads. Como o deploy
roda `alembic upgrade head && uvicorn`, isso nao e um aviso: e o container que
nao sobe, porque o Alembic recusa "upgrade head" com mais de um head e o `&&`
corta antes do uvicorn.

Merge puro — nao ha schema a mexer aqui, os dois lados ja fizeram o que
tinham que fazer.

⚠ Bancos que rodaram `7f4b0183bfc7` fora do controle do Alembic (aplicada a
mao a partir da maquina de quem a escreveu) vao ve-la rodar de novo ao chegar
aqui. E inofensivo: o upgrade dela e
`ALTER TYPE ... ADD VALUE IF NOT EXISTS 'planilha'`, que e no-op quando o
valor ja existe.

Revision ID: c7d2a04f8b16
Revises: 7f4b0183bfc7, b3f9c17e4a28
"""
from typing import Sequence, Union

revision: str = "c7d2a04f8b16"
down_revision: Union[str, Sequence[str], None] = ("7f4b0183bfc7", "b3f9c17e4a28")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
