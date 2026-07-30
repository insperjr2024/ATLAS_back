from sqlalchemy.orm import Session
from src.repositories.configuracao_repository import ConfiguracaoRepository


class GetConfiguracaoUseCase:
    def __init__(self, db: Session):
        self.repository = ConfiguracaoRepository(db)

    def execute(self):
        configuracao = self.repository.get()
        if not configuracao:
            configuracao = self.repository.criar_padrao()
        return {
            "id": configuracao.id,
            "vagas_por_banca": configuracao.vagas_por_banca
        }