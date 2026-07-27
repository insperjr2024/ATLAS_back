from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Avaliacao:
    id: Optional[int] = None
    banca_id: Optional[int] = None
    avaliador_id: Optional[int] = None
    formulario_id: Optional[int] = None
    status: str = "rascunho"
    comentario_feedback: Optional[str] = None
    submetida_em: Optional[datetime] = None