from dataclasses import dataclass
from typing import Optional


@dataclass
class UsuarioFrente:
    id: Optional[int] = None
    usuario_id: Optional[int] = None
    frente_id: Optional[int] = None