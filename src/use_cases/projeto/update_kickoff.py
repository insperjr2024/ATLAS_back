from datetime import date

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository


class UpdateKickoffRequest(BaseModel):
    data_kickoff: date


class UpdateKickoffUseCase:
    """Só registra a data — marcar o kickoff não move mais o status sozinho.

    Isso é o que permite cadastrar o projeto agora com um kickoff planejado
    pro futuro (§5.2): o projeto continua Vendido até alguém escolher
    Ambientação no seletor de etapa (`UpdateStatusUseCase`), que só libera
    esse destino depois que esta data existir. Corrigir uma data já marcada
    passa pelo mesmo caminho, sem tratamento especial.
    """

    def __init__(self, db: Session):
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: UpdateKickoffRequest):
        projeto = self.repository.update(projeto_id, data_kickoff=request.data_kickoff)
        if not projeto:
            return None
        return {"id": projeto.id, "data_kickoff": projeto.data_kickoff, "status": projeto.status}


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
