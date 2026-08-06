from sqlalchemy.orm import Session

from src.repositories.solicitacao_troca_repository import SolicitacaoTrocaRepository
from src.use_cases.solicitacao_troca.get_solicitacao_troca import serializar_solicitacao_troca
from src.utils.exceptions import RegraDeNegocioError


class CancelarSolicitacaoTrocaUseCase:
    def __init__(self, db: Session):
        self.repository = SolicitacaoTrocaRepository(db)

    def execute(self, solicitacao_id: int, usuario_id: int, eh_diretor: bool = False):
        solicitacao = self.repository.get_by_id(solicitacao_id)
        if not solicitacao:
            raise RegraDeNegocioError("Solicitação de troca não encontrada")

        if solicitacao.status != "pendente":
            raise RegraDeNegocioError("Esta solicitação de troca já foi resolvida")

        if solicitacao.usuario_original_id != usuario_id and not eh_diretor:
            raise RegraDeNegocioError("Só quem abriu o pedido (ou a diretoria) pode cancelá-lo")

        solicitacao = self.repository.update(solicitacao_id, status="cancelada")
        return serializar_solicitacao_troca(solicitacao)
