from sqlalchemy import Column, ForeignKey, Integer
from src.database.database import Base


class DesempenhoMentoriaModel(Base):
    """Vínculo mentor <-> mentorado. Elegibilidade de mentor é
    `usuario.posicao in POSICOES_ELEGIVEIS_MENTOR` (coordenador, gerente ou
    diretor — ver `create_mentoria.py`), checada na camada de use case, não
    aqui — o vínculo em si é escolha manual do admin. Um mentorado só tem 1
    mentor por vez; um mentor pode ter vários."""

    __tablename__ = "desempenho_mentoria"

    id = Column(Integer, primary_key=True, index=True)
    mentor_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    mentorado_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, unique=True, index=True)
