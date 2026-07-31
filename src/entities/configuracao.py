from dataclasses import dataclass
from typing import Optional


@dataclass
class Configuracao:
    id: Optional[int] = None
    vagas_por_banca: int = 5
    cargo_padrao_id: Optional[int] = None