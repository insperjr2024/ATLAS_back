"""tipo_de_notificacao_que_faltava_no_enum

`descricao_coordenador_pendente` é emitido por `marcar_banca_escopo` desde o
commit 3035559, mas nunca foi declarado no enum de `notificacao.tipo`.

Como a coluna é ENUM, o INSERT falhava com *"Data truncated for column 'tipo'"*
— e, por estar dentro da mesma transação, derrubava o **registro de realização
da banca inteiro**. Na tela isso aparecia como "Failed to fetch": a resposta
morria no meio e o navegador não distingue isso de servidor fora do ar.

⚠ A lista abaixo é escrita por extenso, e não derivada do modelo, de propósito:
uma migration precisa descrever o estado daquele momento. Se ela lesse o enum
atual, reescrever o modelo amanhã mudaria o que esta migration faz no passado.

Revision ID: d3a7b91c5e04
Revises: c58f1e7a3d90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d3a7b91c5e04"
down_revision: Union[str, Sequence[str], None] = "c58f1e7a3d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ANTES = [
    "alocado_em_projeto",
    "entrega_registrada",
    "banca_remarcada",
    "entrega_alterada",
    "escalacao_banca",
    "troca_banca",
    "avaliacao_pendente",
    "banca_aviso",
    "lote_desempenho_aberto",
    "pdi_prazo_proximo",
    "pdi_prazo_vencido",
    "kickoff_pendente",
    "tarefa_vencida",
    "banca_nao_marcada",
    "projeto_sem_reuniao",
    "banca_hoje",
    "reajuste_solicitado",
    "reajuste_respondido",
]
DEPOIS = ANTES + ["descricao_coordenador_pendente"]


def _redefinir(valores) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        from src.utils.alembic_pg import redefinir_enum_postgres

        redefinir_enum_postgres(op, "notificacao", "tipo", "tipo_notificacao", list(valores))
    else:
        op.alter_column(
            "notificacao",
            "tipo",
            type_=sa.Enum(*valores, name="tipo_notificacao"),
            existing_nullable=False,
        )


def upgrade() -> None:
    _redefinir(DEPOIS)


def downgrade() -> None:
    # Apagar antes de estreitar: com linhas usando o valor que sai, o MySQL
    # trunca em silêncio e o Postgres recusa o ALTER.
    op.execute("DELETE FROM notificacao WHERE tipo = 'descricao_coordenador_pendente'")
    _redefinir(ANTES)
