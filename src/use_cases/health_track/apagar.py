"""Apagar avaliações do Health Track (2026-10-08, a pedido: a diretoria vai
testar bastante e precisa desfazer).

Um ciclo (um preenchimento, todas as linhas com o mesmo `avaliado_em`) ou
tudo: avaliações, rodadas e ações, zerando a contagem. Só a diretoria de
projetos, pela rota.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from src.models.health_track_acao_model import HealthTrackAcaoModel
from src.models.health_track_rodada_model import HealthTrackRodadaModel, HealthTrackRodadaProjetoModel
from src.repositories.health_track_avaliacao_repository import HealthTrackAvaliacaoRepository
from src.repositories.health_track_rodada_repository import (
    HealthTrackRodadaProjetoRepository,
    HealthTrackRodadaRepository,
)
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import normalizar_utc


class ApagarCicloUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = HealthTrackAvaliacaoRepository(db)
        self.rodada_repo = HealthTrackRodadaRepository(db)
        self.item_repo = HealthTrackRodadaProjetoRepository(db)

    def execute(self, projeto_id: int, avaliado_em: datetime) -> dict:
        avaliado_em = normalizar_utc(avaliado_em)
        apagadas = self.repository.apagar_ciclo(projeto_id, avaliado_em)
        if not apagadas:
            raise RegraDeNegocioError("Esse ciclo não existe mais.")
        # Se era o ciclo que marcou o projeto como avaliado na rodada aberta,
        # ele volta pra pendente: a rodada não pode fechar em cima de uma
        # avaliação que não existe.
        rodada = self.rodada_repo.get_aberta()
        if rodada:
            item = self.item_repo.get_item(rodada.id, projeto_id)
            if item and item.situacao == "avaliada":
                restantes = [a for a in self.repository.get_historico(projeto_id) if a.avaliado_em >= rodada.aberta_em]
                if not restantes:
                    self.item_repo.update(item.id, situacao="pendente", resolvido_em=None, resolvido_por=None)
        return {"apagadas": apagadas}


class ZerarHealthTrackUseCase:
    """Apaga TODAS as avaliações, rodadas e ações. Pilares e regra ficam."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self) -> dict:
        acoes = self.db.query(HealthTrackAcaoModel).delete(synchronize_session=False)
        self.db.query(HealthTrackRodadaProjetoModel).delete(synchronize_session=False)
        rodadas = self.db.query(HealthTrackRodadaModel).delete(synchronize_session=False)
        avaliacoes = HealthTrackAvaliacaoRepository(self.db).apagar_todas()
        self.db.commit()
        return {"avaliacoes": avaliacoes, "rodadas": rodadas, "acoes": acoes}
