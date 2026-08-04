from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Banca:
    id: Optional[int] = None
    nome_projeto: str = ""
    escopo_id: Optional[int] = None
    coordenador_id: Optional[int] = None
    data_hora: Optional[datetime] = None
    # F5 — a costura com o projeto. Entity e model não têm trava de sincronia:
    # campo que existe só aqui é aceito pela API e descartado em silêncio.
    projeto_escopo_id: Optional[int] = None
    realizado_em: Optional[datetime] = None
    resultado: Optional[str] = None
    excecao_choque_por: Optional[int] = None
    excecao_choque_nota: Optional[str] = None
