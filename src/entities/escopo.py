from dataclasses import dataclass
from typing import Optional


@dataclass
class Escopo:
    id: Optional[int] = None
    nome: str = ""
    frente_id: Optional[int] = None
    ativo: bool = True