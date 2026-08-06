from sqlalchemy.orm import Session
from src.repositories.solicitacao_troca_repository import SolicitacaoTrocaRepository


def serializar_solicitacao_troca(s):
    return {
        "id": s.id,
        "banca_id": s.banca_id,
        "usuario_original_id": s.usuario_original_id,
        "candidatura_id": s.candidatura_id,
        "status": s.status,
        "criado_em": s.criado_em,
        "confirmada_por": s.confirmada_por,
        "confirmada_em": s.confirmada_em,
    }


class ListSolicitacoesTrocaUseCase:
    """Lista tudo — o front filtra "as que eu poderia confirmar" e "as
    minhas", igual o resto do app filtra listas pequenas no cliente."""

    def __init__(self, db: Session):
        self.repository = SolicitacaoTrocaRepository(db)

    def execute(self):
        return [serializar_solicitacao_troca(s) for s in self.repository.get_all()]
