from datetime import date

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository
from src.use_cases.notificacao.eventos import notificar_entrega_alterada
from src.use_cases.projeto.encerrar_ambientacao import EncerrarAmbientacaoUseCase


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
        self.db = db
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: UpdateKickoffRequest):
        projeto = self.repository.update(projeto_id, data_kickoff=request.data_kickoff)
        if not projeto:
            return None
        # 🤖 O kickoff é de onde a ambientação conta: corrigi-lo para trás pode
        # já ter encerrado a janela (§5.3). Recheca na hora, para o status não
        # ficar desencontrado da data até a passada da madrugada.
        EncerrarAmbientacaoUseCase(self.db).executar_para(projeto_id)
        atualizado = self.repository.get_by_id(projeto_id)
        return {
            "id": atualizado.id,
            "data_kickoff": atualizado.data_kickoff,
            "status": atualizado.status,
        }


class UpdateEntregaClienteRequest(BaseModel):
    data_entrega_cliente: date


class UpdateEntregaClienteUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: UpdateEntregaClienteRequest):
        anterior = self.repository.get_by_id(projeto_id)
        if not anterior:
            return None
        data_antiga = anterior.data_entrega_cliente

        projeto = self.repository.update(projeto_id, data_entrega_cliente=request.data_entrega_cliente)
        if not projeto:
            return None

        # Só quando MUDA uma data que já existia. Preencher pela primeira vez é
        # planejamento, não remarcação — quem está no projeto acabou de fazer
        # isso e não precisa ser avisado do próprio clique.
        if data_antiga is not None and data_antiga != projeto.data_entrega_cliente:
            notificar_entrega_alterada(
                self.db, projeto, data_antiga, projeto.data_entrega_cliente
            )

        return {"id": projeto.id, "data_entrega_cliente": projeto.data_entrega_cliente}
