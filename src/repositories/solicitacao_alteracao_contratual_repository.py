from typing import List

from src.models.solicitacao_alteracao_contratual_model import SolicitacaoAlteracaoContratualModel
from src.repositories.base_repository import BaseRepository


class SolicitacaoAlteracaoContratualRepository(BaseRepository[SolicitacaoAlteracaoContratualModel]):
    model = SolicitacaoAlteracaoContratualModel

    def list_by_documento(self, documento_id: int) -> List[SolicitacaoAlteracaoContratualModel]:
        """Todas as solicitações de um documento, da mais recente pra mais
        antiga — inclui as já analisadas, o histórico interessa pro Jurídico."""
        return (
            self.db.query(SolicitacaoAlteracaoContratualModel)
            .filter(SolicitacaoAlteracaoContratualModel.documento_id == documento_id)
            .order_by(SolicitacaoAlteracaoContratualModel.criado_em.desc())
            .all()
        )

    def marcar_analisada(
        self, registro: SolicitacaoAlteracaoContratualModel
    ) -> SolicitacaoAlteracaoContratualModel:
        registro.status = "analisada"
        self.db.commit()
        self.db.refresh(registro)
        return registro
