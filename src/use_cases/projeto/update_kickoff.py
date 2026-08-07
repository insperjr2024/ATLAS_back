from datetime import date
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.entrega_alteracao_repository import EntregaAlteracaoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.use_cases.notificacao.eventos import notificar_entrega_alterada
from src.use_cases.projeto.encerrar_ambientacao import EncerrarAmbientacaoUseCase
from src.utils.exceptions import RegraDeNegocioError


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


# ⭐ **Não existe "marcar a entrega ao cliente" do projeto.** Entrega ao cliente
# e entrega do escopo são a MESMA coisa: o cliente recebe quando o escopo é
# entregue (§5.5). Quem escreve isso é `RegistrarEntregaEscopoUseCase`, uma
# data por escopo; a do projeto é derivada da última delas em
# `serializar_projeto_completo`.
#
# Havia aqui um `UpdateEntregaClienteUseCase` escrevendo
# `projeto.data_entrega_cliente` por fora — duas datas para a mesma promessa,
# que divergiam no primeiro reagendamento de escopo.
