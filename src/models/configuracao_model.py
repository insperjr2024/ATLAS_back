from sqlalchemy import Column, Integer, ForeignKey
from src.database.database import Base


class ConfiguracaoModel(Base):
    """Ajustes globais do sistema — uma linha só, editável pela diretoria.

    A carga de trabalho NÃO mora aqui: ela é uma escala de estados por papel,
    em `situacao_carga`. Um número único não descrevia o que a diretoria
    precisava dizer ("2 é o ideal, 3 já é demais").
    """

    __tablename__ = "configuracao"

    id = Column(Integer, primary_key=True, index=True)
    vagas_por_banca = Column(Integer, nullable=False, default=5)
    cargo_padrao_id = Column(Integer, ForeignKey("cargo.id"), nullable=True)