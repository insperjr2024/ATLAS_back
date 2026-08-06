from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.cronograma_reajuste_repository import CronogramaReajusteRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.use_cases.cronograma_reajuste.solicitar import nome_do_escopo, serializar_solicitacao
from src.use_cases.notificacao.eventos import notificar_reajuste_respondido
from src.utils.exceptions import RegraDeNegocioError


class ResponderReajusteRequest(BaseModel):
    aprovado: bool
    justificativa: str


class ResponderReajusteUseCase:
    """A única saída da trava de `cronograma_guard.py` (§5.6). Aprovar limpa
    `projeto_escopo.cronograma_oficializado_em`: o coordenador volta a poder
    editar as etapas, e oficializa de novo quando terminar."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = CronogramaReajusteRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, solicitacao_id: int, request: ResponderReajusteRequest, current_user) -> dict:
        solicitacao = self.repository.get_by_id(solicitacao_id)
        if not solicitacao:
            raise RegraDeNegocioError("Solicitação não encontrada")
        if solicitacao.status != "pendente":
            raise RegraDeNegocioError("Esta solicitação já foi respondida")
        if not (request.justificativa or "").strip():
            raise RegraDeNegocioError("Digite uma justificativa para a decisão")

        novo_status = "aprovado" if request.aprovado else "rejeitado"
        atualizado = self.repository.update(
            solicitacao_id,
            status=novo_status,
            respondido_por=current_user.id,
            resposta_justificativa=request.justificativa.strip(),
            respondido_em=datetime.now(),
        )

        escopo = self.escopo_repository.get_by_id(solicitacao.projeto_escopo_id)
        if request.aprovado and escopo:
            self.escopo_repository.update(escopo.id, cronograma_oficializado_em=None)

        if escopo:
            notificar_reajuste_respondido(
                self.db,
                solicitacao.solicitado_por,
                escopo.projeto_id,
                escopo.id,
                solicitacao_id,
                nome_do_escopo(escopo, self.catalogo_repository),
                request.aprovado,
                request.justificativa.strip(),
            )

        return serializar_solicitacao(atualizado)
