from dataclasses import dataclass
from typing import Optional


@dataclass
class EquipeProjeto:
    id: Optional[int] = None
    banca_id: Optional[int] = None
    usuario_id: Optional[int] = None