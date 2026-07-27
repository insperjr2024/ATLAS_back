from dataclasses import dataclass
from typing import Optional


@dataclass
class BancaFrente:
    id: Optional[int] = None
    banca_id: Optional[int] = None
    frente_id: Optional[int] = None