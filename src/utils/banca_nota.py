from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict
from src.models.avaliacao_nota_model import AvaliacaoNotaModel


def calcular_nota_final(notas: List[AvaliacaoNotaModel]) -> Optional[Decimal]:
    valores = [n.nota for n in notas if n.nota is not None]
    if not valores:
        return None
    media = sum(valores) / len(valores)
    return media.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_notas_por_pergunta(notas: List[AvaliacaoNotaModel]) -> Dict[int, Decimal]:
    por_pergunta: Dict[int, list] = {}
    for n in notas:
        if n.nota is None:
            continue
        por_pergunta.setdefault(n.pergunta_id, []).append(n.nota)
    return {
        pergunta_id: (sum(valores) / len(valores)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for pergunta_id, valores in por_pergunta.items()
    }