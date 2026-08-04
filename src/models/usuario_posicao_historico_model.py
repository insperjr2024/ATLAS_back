from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.sql import func
from src.database.database import Base


class UsuarioPosicaoHistoricoModel(Base):
    """Quem era o quê, quando.

    Sem isso, a promoção da virada reescreveria o passado: o arquivo de 2026.1
    mostraria a Ana como coordenadora, e não como a consultora que ela era.
    """

    __tablename__ = "usuario_posicao_historico"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    posicao = Column(
        Enum("diretor", "gerente", "coordenador", "consultor", name="posicao_historico"),
        nullable=False,
    )
    semestre_id = Column(Integer, ForeignKey("semestre.id"), nullable=True)
    alterado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    alterado_em = Column(DateTime, nullable=False, server_default=func.now())
