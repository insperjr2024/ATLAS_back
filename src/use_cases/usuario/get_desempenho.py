from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from src.repositories.avaliacao_repository import AvaliacaoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.semestre_repository import SemestreRepository
from src.utils.identificar_semestre import identificar_semestre
from src.utils.desempenho_consultor import calcular_desempenho_consultor


class GetDesempenhoUseCase:
    def __init__(self, db: Session):
        self.avaliacao_repository = AvaliacaoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, usuario_id: int, semestre_id: Optional[int] = None):
        semestres = self.semestre_repository.get_all()

        if semestre_id is not None:
            semestre = next((s for s in semestres if s.id == semestre_id), None)
        else:
            semestre = identificar_semestre(datetime.now(), semestres)

        if not semestre:
            return None

        avaliacoes = self.avaliacao_repository.get_all()
        bancas = self.banca_repository.get_all()

        return calcular_desempenho_consultor(usuario_id, semestre, avaliacoes, bancas)