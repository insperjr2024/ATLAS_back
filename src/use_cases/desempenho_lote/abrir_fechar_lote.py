from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.use_cases.desempenho_lote.get_lote import serializar_lote
from src.use_cases.desempenho_lote.get_pendencias import GetPendenciasLoteUseCase
from src.use_cases.notificacao.eventos import notificar_lote_desempenho

# Regra 2.6: nada de DELETE aqui — fechar é sempre um update de
# `override_manual`, nunca a remoção do lote.


class _MudarOverrideLoteUseCase:
    override_manual: Optional[str]

    def __init__(self, db: Session):
        self.db = db
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)

    def execute(self, lote_id: int) -> Optional[dict]:
        lote = self.lote_repo.update(lote_id, override_manual=self.override_manual)
        if not lote:
            return None
        return serializar_lote(lote, self.lote_projeto_repo.get_projeto_ids(lote_id))


class AbrirLoteUseCase(_MudarOverrideLoteUseCase):
    override_manual = "aberto"

    def execute(self, lote_id: int) -> Optional[dict]:
        resultado = super().execute(lote_id)
        if resultado is None:
            return None

        # Abrir o lote é o momento em que as avaliações passam a existir para
        # quem responde — antes disso, avisar seria cobrar algo que a pessoa
        # nem consegue abrir. A `chave_dedup` é por lote+pessoa, então reabrir
        # um lote já anunciado não dispara aviso de novo.
        lote = self.lote_repo.get_by_id(lote_id)
        pendencias = GetPendenciasLoteUseCase(self.db).execute(lote_id) or []
        notificar_lote_desempenho(self.db, lote, pendencias)

        return resultado


class FecharLoteUseCase(_MudarOverrideLoteUseCase):
    override_manual = "fechado"


class SeguirDatasLoteUseCase(_MudarOverrideLoteUseCase):
    override_manual = None
