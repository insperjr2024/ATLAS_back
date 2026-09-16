from datetime import datetime
from typing import Optional

from src.utils.fuso import agora_utc

# Nome escolhido de propósito diferente de `desempenho_consultor.py`, que já
# existe e é o "% de bancas atendidas" do dashboard atual — não confundir.


def esta_aberto(
    override_manual: Optional[str],
    data_inicio: datetime,
    data_fim: datetime,
    agora: Optional[datetime] = None,
) -> bool:
    """Abertura de um lote de desempenho é tri-state, não booleana (regra 2.1):
    `override_manual` NULL segue as datas (calculado, nunca gravado);
    "aberto"/"fechado" força, ignorando as datas até alguém voltar pro
    automático. Este é o único lugar que decide isso.

    ⚠ `data_inicio`/`data_fim` nascem em UTC (`agora_utc()`, tanto na
    finalização automática quanto no lote manual que o front cria com
    `toISOString()`) — comparar com `datetime.now()` local errava por 3h
    (2026-09-16: o lembrete de prazo disparava depois do prazo já ter
    passado, e o formulário ficava aceitando resposta por 3h a mais depois
    do fim de verdade). Mesma régua de `banca.data_hora` em `fuso.py`.
    """
    if override_manual == "aberto":
        return True
    if override_manual == "fechado":
        return False
    agora = agora or agora_utc()
    return data_inicio <= agora <= data_fim
