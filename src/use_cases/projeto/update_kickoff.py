from datetime import date
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.entrega_alteracao_repository import EntregaAlteracaoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.use_cases.notificacao.eventos import notificar_entrega_alterada
from src.use_cases.projeto.encerrar_ambientacao import EncerrarAmbientacaoUseCase
from src.utils.exceptions import RegraDeNegocioError


class UpdateKickoffRequest(BaseModel):
    data_kickoff: date


class UpdateKickoffUseCase:
    """⭐ §4: *"Vendido → Ambientação **ao marcar o kickoff**"*.

    A transição é do sistema, não de quem clica: marcar a data JÁ é a decisão
    de que o projeto começou. Exigir um segundo passo no seletor de etapa
    deixava todo projeto parado em Vendido com kickoff marcado — um estado que
    o §4 não prevê e que ninguém entende ao abrir a tela.

    Vale só a partir de **Vendido**. Corrigir a data de um projeto que já
    avançou não o puxa de volta: voltar etapa é decisão manual (§4), e um
    acerto de data não pode desfazê-la.

    Kickoff no futuro não é caso especial. O projeto entra em Ambientação
    agora, e a janela dela é contada a partir da data marcada por
    `EncerrarAmbientacaoUseCase` — se a data ainda não chegou, a janela
    simplesmente não venceu.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)

    def execute(self, projeto_id: int, request: UpdateKickoffRequest, alterado_por=None):
        projeto = self.repository.update(projeto_id, data_kickoff=request.data_kickoff)
        if not projeto:
            return None

        # 🤖 `alterado_por=None` de propósito quando ninguém é informado: o
        # histórico mostra "Automático", que é a verdade — a pessoa marcou uma
        # data, não escolheu uma etapa.
        if projeto.status == "vendido":
            self.repository.update(projeto_id, status="ambientacao")
            self.historico_repository.create(
                projeto_id=projeto_id,
                status_anterior="vendido",
                status_novo="ambientacao",
                alterado_por=alterado_por,
            )
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
