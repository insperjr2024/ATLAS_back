from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Projeto:
    id: Optional[int] = None
    nome: str = ""
    cliente: str = ""
    descricao: Optional[str] = None
    link_proposta: Optional[str] = None
    status: str = "vendido"
    dias_ambientacao: int = 5
    data_kickoff: Optional[date] = None
    data_entrega_cliente: Optional[date] = None
    dia_reuniao_padrao: Optional[int] = None
    criado_por: Optional[int] = None
    status_antes_pausa: Optional[str] = None
