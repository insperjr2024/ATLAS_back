from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.use_cases.desempenho_lote.get_lote import serializar_lote

# Regra 2.6: nada de DELETE aqui — fechar é sempre um update de
# `override_manual`, nunca a remoção do lote.


class _MudarOverrideLoteUseCase:
    override_manual: Optional[str]

    def __init__(self, db: Session):
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)

    def execute(self, lote_id: int) -> Optional[dict]:
        lote = self.lote_repo.update(lote_id, override_manual=self.override_manual)
        if not lote:
            return None
        return serializar_lote(lote, self.lote_projeto_repo.get_projeto_ids(lote_id))


class AbrirLoteUseCase(_MudarOverrideLoteUseCase):
    override_manual = "aberto"


class FecharLoteUseCase(_MudarOverrideLoteUseCase):
    override_manual = "fechado"


class SeguirDatasLoteUseCase(_MudarOverrideLoteUseCase):
    override_manual = None
