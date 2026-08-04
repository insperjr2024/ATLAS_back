from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.status_projeto import (
    aplicar_transicao_manual,
    pausar,
    retomar,
    status_anterior_manual,
    transicao_manual_valida,
    transicao_volta_valida,
)


class UpdateStatusRequest(BaseModel):
    #: A próxima etapa, a ANTERIOR (volta), ou "pausado" / "retomar".
    status_novo: str


class UpdateStatusUseCase:
    """✋ As transições manuais do §4 — Coord (Dir/Ger herdam); Cons não.

    Anda para frente e **para trás**, um passo por vez. A volta existe porque
    avançar sem desfazer deixa um clique errado travando o projeto até alguém
    mexer no banco. Toda transição, nos dois sentidos, grava no histórico.
    """

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

        elif transicao_volta_valida(anterior, request.status_novo):
            # A volta nunca mexe em `data_kickoff`: Ambientação é o piso, e
            # de lá não se regride para Vendido.
            novo_status = request.status_novo
            self.repository.update(projeto_id, status=novo_status)

        elif transicao_manual_valida(anterior, request.status_novo):
            novo_status = request.status_novo
            self.repository.update(projeto_id, status=novo_status)

        else:
            raise RegraDeNegocioError(
                f"'{request.status_novo}' não é um passo válido a partir de "
                f"'{anterior}'. O projeto anda uma etapa por vez: "
                f"{_descrever_passos(anterior)}."
            )

        self.historico_repository.create(
            projeto_id=projeto_id,
            status_anterior=anterior,
            status_novo=novo_status,
            alterado_por=alterado_por,
        )
        return {"id": projeto_id, "status_anterior": anterior, "status": novo_status}


def _descrever_passos(status_atual: str) -> str:
    """Os destinos válidos daqui, para a mensagem de erro ser acionável."""
    from src.utils.status_projeto import TRANSICOES_MANUAIS

    opcoes = []
    anterior = status_anterior_manual(status_atual)
    if anterior:
        opcoes.append(f"voltar para '{anterior}'")
    proximo = TRANSICOES_MANUAIS.get(status_atual)
    if proximo:
        opcoes.append(f"avançar para '{proximo}'")
    if status_atual == "pausado":
        opcoes.append("'retomar'")
    return ", ".join(opcoes) if opcoes else "não há transição manual daqui"
