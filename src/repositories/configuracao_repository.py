from sqlalchemy.orm import Session
from src.models.configuracao_model import ConfiguracaoModel
from typing import Optional


class ConfiguracaoRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self) -> Optional[ConfiguracaoModel]:
        return self.db.query(ConfiguracaoModel).first()

    def criar_padrao(self, vagas_por_banca: int = 5) -> ConfiguracaoModel:
        configuracao = ConfiguracaoModel(vagas_por_banca=vagas_por_banca)
        self.db.add(configuracao)
        self.db.commit()
        self.db.refresh(configuracao)
        return configuracao

    def update(self, **kwargs) -> Optional[ConfiguracaoModel]:
        configuracao = self.get()
        if not configuracao:
            return None
        for key, value in kwargs.items():
            setattr(configuracao, key, value)
        self.db.commit()
        self.db.refresh(configuracao)
        return configuracao