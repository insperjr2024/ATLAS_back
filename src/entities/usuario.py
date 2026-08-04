from dataclasses import dataclass
from typing import Optional


@dataclass
class Usuario:
    id: Optional[int] = None
    nome: str = ""
    email_insper: str = ""
    senha_hash: str = ""
    cargo_id: Optional[int] = None
    posicao: str = "consultor"
    status: str = "ativo"
    ativo: bool = True