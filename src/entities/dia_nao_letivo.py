from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class DiaNaoLetivo:
    id: Optional[int] = None
    semestre_id: Optional[int] = None
    data: Optional[date] = None
    tipo: str = "feriado"
    descricao: Optional[str] = None
