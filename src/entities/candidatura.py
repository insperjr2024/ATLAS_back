from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Candidatura:
    id: Optional[int] = None
    banca_id: Optional[int] = None
    usuario_id: Optional[int] = None
    criado_em: Optional[datetime] = None
    confirmado: bool = False