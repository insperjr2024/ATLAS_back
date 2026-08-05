from dataclasses import dataclass
from typing import Optional


@dataclass
class Cargo:
    id: Optional[int] = None
    nome: str = ""
    pode_definir_formulario: bool = False
    pode_agendar_banca: bool = False
    pode_gerenciar_cargos: bool = False
    pode_gerenciar_membros: bool = False
    pode_gerenciar_nucleo: bool = False