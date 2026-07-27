from dataclasses import dataclass
from typing import Optional


@dataclass
class Usuario:
    id: Optional[int] = None
    nome: str = ""
    email_insper: str = ""
    cargo_id: Optional[int] = None
    ativo: bool = True