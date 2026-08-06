from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.use_cases.projeto.encerrar_ambientacao import EncerrarAmbientacaoUseCase
from src.utils.exceptions import RegraDeNegocioError
from src.utils.status_projeto import (
    destinos_validos,
    pausar,
    retomar,
    transicao_manual_valida,
)


class UpdateStatusRequest(BaseModel):
    #: Qualquer etapa ativa, ou "pausado" / "retomar".
    status_novo: str


class UpdateStatusUseCase:
    """✋ As transições manuais do §4 — Coord (Dir/Ger herdam); Cons não.

    Livre entre as etapas ativas, nos dois sentidos (inclusive reabrir um
    projeto finalizado). Vendido só sai pra Ambientação, e só com kickoff já
    marcado. Toda transição, em qualquer sentido, grava no histórico.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)

    def execute(self, projeto_id: int, request: UpdateStatusRequest, alterado_por: Optional[int] = None):
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None

        anterior = projeto.status
        tem_kickoff = projeto.data_kickoff is not None

        if request.status_novo == "pausado":
            novo_status, status_a_guardar = pausar(anterior)
            self.repository.update(projeto_id, status=novo_status, status_antes_pausa=status_a_guardar)

        elif request.status_novo == "retomar":
            novo_status = retomar(projeto.status_antes_pausa)
            self.repository.update(projeto_id, status=novo_status, status_antes_pausa=None)

        elif transicao_manual_valida(anterior, request.status_novo, tem_kickoff):
            novo_status = request.status_novo
            self.repository.update(projeto_id, status=novo_status)

        else:
            destinos = destinos_validos(anterior, tem_kickoff)
            descricao = ", ".join(f"'{d}'" for d in destinos) if destinos else "nenhuma (kickoff ainda não marcado)"
            raise RegraDeNegocioError(
                f"'{request.status_novo}' não é um destino válido a partir de "
                f"'{anterior}'. Etapas disponíveis: {descricao}."
            )

        self.historico_repository.create(
            projeto_id=projeto_id,
            status_anterior=anterior,
            status_novo=novo_status,
            alterado_por=alterado_por,
        )

        # 🤖 Entrou em Ambientação com a janela já vencida (kickoff antigo, ou
        # o projeto ficou parado em Vendido): a virada é imediata, e não na
        # passada da madrugada — a alternativa seria a tela mostrar
        # "Ambientação" por um dia sabendo que ela acabou. As duas linhas
        # ficam no histórico, que é o registro fiel do que aconteceu.
        if novo_status == "ambientacao" and EncerrarAmbientacaoUseCase(self.db).executar_para(
            projeto_id
        ):
            return {"id": projeto_id, "status_anterior": anterior, "status": "em_andamento"}

        return {"id": projeto_id, "status_anterior": anterior, "status": novo_status}
