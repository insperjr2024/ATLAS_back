from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


@dataclass
class AvaliacaoNota:
    id: Optional[int] = None
    avaliacao_id: Optional[int] = None
    pergunta_id: Optional[int] = None
    nota: Optional[Decimal] = None
    resposta_texto: Optional[str] = None