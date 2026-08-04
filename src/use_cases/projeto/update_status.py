from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.utils.status_projeto import (
    aplicar_transicao_manual,
    pausar,
    retomar,
    transicao_manual_valida,
)


class UpdateStatusRequest(BaseModel):
    status_novo: str  # próxima etapa manual, ou "pausado" / "retomar"


class UpdateStatusUseCase:
    """✋ As transições manuais do §4 — Coord (Dir/Ger herdam); Cons não."""

    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)

    def execute(self, projeto_id: int, request: UpdateStatusRequest, alterado_por: Optional[int] = None):
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None

        anterior = projeto.status

        if request.status_novo == "pausado":
            novo_status, status_a_guardar = pausar(anterior)
            self.repository.update(projeto_id, status=novo_status, status_antes_pausa=status_a_guardar)
        elif request.status_novo == "retomar":
            novo_status = retomar(projeto.status_antes_pausa)
            self.repository.update(projeto_id, status=novo_status, status_antes_pausa=None)
        else:
            if not transicao_manual_valida(anterior, request.status_novo):
                aplicar_transicao_manual(anterior)  # levanta RegraDeNegocioError com a mensagem certa
            novo_status = request.status_novo
            self.repository.update(projeto_id, status=novo_status)

        self.historico_repository.create(
            projeto_id=projeto_id,
            status_anterior=anterior,
            status_novo=novo_status,
            alterado_por=alterado_por,
        )
        return {"id": projeto_id, "status_anterior": anterior, "status": novo_status}
