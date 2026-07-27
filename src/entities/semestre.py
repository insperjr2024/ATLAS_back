from dataclasses import dataclass
from typing import Optional
from datetime import date


@dataclass
class Semestre:
    id: Optional[int] = None
    nome: str = ""
    inicio: Optional[date] = None
    fim: Optional[date] = None