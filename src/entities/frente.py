from dataclasses import dataclass
from typing import Optional


@dataclass
class Frente:
    id: Optional[int] = None
    nome: str = ""