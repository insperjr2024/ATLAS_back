from datetime import datetime
from typing import Optional

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
    automático. Este é o único lugar que decide isso."""
    if override_manual == "aberto":
        return True
    if override_manual == "fechado":
        return False
    agora = agora or datetime.now()
    return data_inicio <= agora <= data_fim
