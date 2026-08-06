from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.cronograma_reajuste_repository import CronogramaReajusteRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.notificacao.eventos import notificar_reajuste_solicitado
from src.utils.exceptions import RegraDeNegocioError


class SolicitarReajusteRequest(BaseModel):
    motivo: str


def serializar_solicitacao(s) -> dict:
    return {
        "id": s.id,
        "projeto_escopo_id": s.projeto_escopo_id,
        "solicitado_por": s.solicitado_por,
        "motivo": s.motivo,
        "status": s.status,
        "respondido_por": s.respondido_por,
        "resposta_justificativa": s.resposta_justificativa,
        "criado_em": s.criado_em,
        "respondido_em": s.respondido_em,
    }


def nome_do_escopo(escopo, catalogo_repository: EscopoRepository) -> str:
    if escopo.nome_customizado:
        return escopo.nome_customizado
    do_catalogo = catalogo_repository.get_by_id(escopo.escopo_id) if escopo.escopo_id else None
    return do_catalogo.nome if do_catalogo else f"escopo {escopo.id}"


class SolicitarReajusteUseCase:
    """§5.6: o pedido do coordenador pra reabrir um cronograma já
    oficializado. Só cria o pedido — quem destrava é a diretoria, em
    `ResponderReajusteUseCase`."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = CronogramaReajusteRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, projeto_escopo_id: int, request: SolicitarReajusteRequest, current_user) -> dict:
        escopo = self.escopo_repository.get_by_id(projeto_escopo_id)
        if not escopo:
            raise RegraDeNegocioError("Escopo não encontrado")
        if not escopo.cronograma_oficializado_em:
            raise RegraDeNegocioError("Este cronograma ainda não foi oficializado — não há o que reajustar")
        if not (request.motivo or "").strip():
            raise RegraDeNegocioError("Descreva o motivo do reajuste")
        if self.repository.get_pendente_do_escopo(projeto_escopo_id):
            raise RegraDeNegocioError("Já existe uma solicitação de reajuste pendente para este escopo")

        solicitacao = self.repository.create(
            projeto_escopo_id=projeto_escopo_id,
            solicitado_por=current_user.id,
            motivo=request.motivo.strip(),
        )

        nome_escopo = nome_do_escopo(escopo, self.catalogo_repository)
        for diretor in self.usuario_repository.get_por_posicao("diretor"):
            notificar_reajuste_solicitado(
                self.db, diretor.id, escopo.projeto_id, escopo.id, nome_escopo, current_user.nome
            )

        return serializar_solicitacao(solicitacao)
