from sqlalchemy.orm import Session
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.avaliacao_repository import AvaliacaoRepository
from src.utils.avaliacoes_pendentes import calcular_avaliacoes_pendentes


class GetBancasParaAvaliarUseCase:
    def __init__(self, db: Session):
        self.candidatura_repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.avaliacao_repository = AvaliacaoRepository(db)

    def execute(self, usuario_id: int):
        candidaturas = self.candidatura_repository.get_by_usuario(usuario_id)
        avaliacoes = self.avaliacao_repository.get_all()
        bancas = self.banca_repository.get_all()
        return calcular_avaliacoes_pendentes(candidaturas, avaliacoes, bancas)