from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class ProjetoMembro:
    id: Optional[int] = None
    projeto_id: Optional[int] = None
    usuario_id: Optional[int] = None
    papel: str = "consultor"
    entrou_em: Optional[date] = None
    saiu_em: Optional[date] = None
