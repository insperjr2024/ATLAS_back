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
    # A costura com o projeto mora em `banca_escopo` (uma banca cobre N
    # escopos), não num campo daqui.
    realizado_em: Optional[datetime] = None
    resultado: Optional[str] = None
    excecao_choque_por: Optional[int] = None
    excecao_choque_nota: Optional[str] = None
