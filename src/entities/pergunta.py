from dataclasses import dataclass
from typing import Optional


@dataclass
class Pergunta:
    id: Optional[int] = None
    formulario_id: Optional[int] = None
    texto: str = ""
    ordem: int = 0
    tipo_resposta: str = "nota"