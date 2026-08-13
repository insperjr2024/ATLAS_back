from sqlalchemy.orm import Session
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.avaliacao_repository import AvaliacaoRepository
from src.repositories.banca_sessao_repository import BancaSessaoRepository
from src.utils.avaliacoes_pendentes import calcular_avaliacoes_pendentes


class GetAvaliacoesPendentesUseCase:
    def __init__(self, db: Session):
        self.candidatura_repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.avaliacao_repository = AvaliacaoRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)

    def execute(self):
        candidaturas = self.candidatura_repository.get_all()
        avaliacoes = self.avaliacao_repository.get_all()
        bancas = self.banca_repository.get_all()
        # A pendência é por sessão: quem avaliou a banca reprovada precisa
        # avaliar a segunda também (§9).
        sessoes = self.sessao_repository.get_by_bancas([b.id for b in bancas])
        sessao_por_banca = {
            banca_id: max((s.numero for s in lista if s.encerrada_em is None), default=1)
            for banca_id, lista in sessoes.items()
        }
        return calcular_avaliacoes_pendentes(
            candidaturas, avaliacoes, bancas, sessao_por_banca=sessao_por_banca
        )