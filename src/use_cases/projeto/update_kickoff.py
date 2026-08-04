from datetime import date
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.utils.exceptions import RegraDeNegocioError


class UpdateKickoffRequest(BaseModel):
    data_kickoff: date


class UpdateKickoffUseCase:
    """🤖 A PRIMEIRA marcação do kickoff dispara Vendido → Ambientação sozinha
    (§5.2). Depois disso, a data fica aberta para correção — vira só um
    campo, sem mexer no status nem gerar novo histórico."""

    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)

    def execute(self, projeto_id: int, request: UpdateKickoffRequest, alterado_por: Optional[int] = None):
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None

        if projeto.data_kickoff is None:
            if projeto.status != "vendido":
                raise RegraDeNegocioError("O kickoff só pode ser marcado enquanto o projeto está Vendido")
            self.repository.update(projeto_id, data_kickoff=request.data_kickoff, status="ambientacao")
            self.historico_repository.create(
                projeto_id=projeto_id,
                status_anterior="vendido",
                status_novo="ambientacao",
                alterado_por=None,  # 🤖 automático — o kickoff é a causa, não uma pessoa clicando "mudar status"
            )
            return {"id": projeto_id, "data_kickoff": request.data_kickoff, "status": "ambientacao"}

        # Kickoff já foi marcado antes — isto é só uma correção de data.
        self.repository.update(projeto_id, data_kickoff=request.data_kickoff)
        return {"id": projeto_id, "data_kickoff": request.data_kickoff, "status": projeto.status}


class UpdateEntregaClienteRequest(BaseModel):
    data_entrega_cliente: date


class UpdateEntregaClienteUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: UpdateEntregaClienteRequest):
        projeto = self.repository.update(projeto_id, data_entrega_cliente=request.data_entrega_cliente)
        if not projeto:
            return None
        return {"id": projeto.id, "data_entrega_cliente": projeto.data_entrega_cliente}
