from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Banca:
    id: Optional[int] = None
    nome_projeto: str = ""
    escopo_id: Optional[int] = None
    coordenador_id: Optional[int] = None
    data_hora: Optional[datetime] = None