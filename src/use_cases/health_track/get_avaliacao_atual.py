from sqlalchemy.orm import Session

from src.repositories.health_track_avaliacao_repository import HealthTrackAvaliacaoRepository
from src.repositories.health_track_pilar_repository import HealthTrackPilarRepository
from src.repositories.health_track_regra_repository import HealthTrackRegraRepository
from src.use_cases.health_track.serializar import nomes_para, serializar_avaliacao, serializar_pilar
from src.utils.health_track_status import ReguasStatus, status_geral_ou_nada


class GetAvaliacaoAtualUseCase:
    """A cor vigente de cada pilar ativo do projeto e o status geral (§4).

    Uma entrada por pilar ATIVO, na ordem de exibição, mesmo sem avaliação
    (`avaliacao: null`) — a tela desenha os pilares a partir daqui e precisa
    saber quais ainda não têm cor. Pilar desativado não aparece aqui, só no
    histórico.

    A última cor é por pilar, não "o último ciclo": um pilar ativado depois
    do último preenchimento fica `null` sem esconder a cor dos outros — e
    deixa o status geral `null` até o próximo preenchimento.
    """

    def __init__(self, db: Session):
        self.db = db
        self.pilar_repo = HealthTrackPilarRepository(db)
        self.repository = HealthTrackAvaliacaoRepository(db)
        self.regra_repo = HealthTrackRegraRepository(db)

    def execute(self, projeto_id: int) -> dict:
        pilares_ativos = self.pilar_repo.get_ativos()
        ultimas = self.repository.get_ultimas_por_pilar(projeto_id)
        pilares, usuarios = nomes_para(self.db, ultimas.values())

        linhas = []
        for pilar in pilares_ativos:
            ultima = ultimas.get(pilar.id)
            linhas.append({
                "pilar": serializar_pilar(pilar),
                "avaliacao": serializar_avaliacao(ultima, pilares, usuarios) if ultima else None,
            })

        avaliadas = [ultimas.get(p.id) for p in pilares_ativos]
        # A regra "da época" do status atual é a do preenchimento mais recente.
        mais_recente = max((a.avaliado_em for a in avaliadas if a), default=None)
        status = status_geral_ou_nada(
            [a.cor if a else None for a in avaliadas],
            mais_recente,
            ReguasStatus(self.regra_repo.get_versoes()),
        )

        return {
            "status_geral": {**status, "avaliado_em": mais_recente} if status else None,
            "pilares": linhas,
        }
