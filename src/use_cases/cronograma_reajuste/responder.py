from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.middlewares.authorization import DIRETORIA_DE_PROJETOS
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
    """A diretoria decide o pedido de dias (§8) — nunca o gerente.

    ⭐ **Aprovar SOMA**, não substitui: dois pedidos de +5 aprovados dão 10
    dias ajustados. É o que o §8 pede ("o total ajustado é a soma dos
    aprovados") e é o que mantém o histórico legível — cada linha continua
    dizendo quanto foi pedido daquela vez.

    ⚠ **`dias_uteis_vendidos` não é tocado aqui, nem em lugar nenhum.** Somar
    no vendido faria o escopo virar "30 dias vendidos" e apagaria para sempre a
    diferença entre ter vendido 30 e ter estourado 20.

    Negar não fecha a porta: dentro do prazo o coordenador pode pedir de novo,
    e a recusa fica registrada.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = CronogramaReajusteRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, solicitacao_id: int, request: ResponderReajusteRequest, current_user) -> dict:
        # Rechecado aqui, e não só na rota: quem pede é validado no use case
        # (`solicitar.py`), e deixar só o gate de rota do outro lado faria a
        # regra mais forte das duas depender de ninguém chamar isto por dentro.
        # Por POSIÇÃO, a única dimensão de permissão desde que `cargo` saiu.
        if getattr(current_user, "posicao", None) not in DIRETORIA_DE_PROJETOS:
            raise RegraDeNegocioError(
                "Só a diretoria de projetos decide um pedido de dias (§8)"
            )

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
            self.escopo_repository.update(
                escopo.id,
                dias_uteis_ajustados=escopo.dias_uteis_ajustados + solicitacao.dias_solicitados,
            )

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
