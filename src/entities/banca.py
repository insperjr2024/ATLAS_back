from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from decimal import Decimal


@dataclass
class Banca:
    id: Optional[int] = None
    nome_projeto: str = ""
    escopo_id: Optional[int] = None
    coordenador_id: Optional[int] = None
    data_hora: Optional[datetime] = None
    status: str = ""
    nota_final: Optional[Decimal] = None