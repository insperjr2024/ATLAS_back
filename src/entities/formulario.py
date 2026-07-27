from dataclasses import dataclass
from typing import Optional


@dataclass
class Formulario:
    id: Optional[int] = None
    semestre_id: Optional[int] = None
    ativo: bool = True