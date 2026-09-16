from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
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
    #: ⚠ Sem FK para `posicao_permissao.posicao` de propósito — é registro
    #: histórico ("a pessoa FOI isto"), e não pode travar a exclusão de um
    #: cargo que ninguém mais ocupa só porque alguém já ocupou um dia.
    posicao = Column(String(50), nullable=False)
    semestre_id = Column(Integer, ForeignKey("semestre.id"), nullable=True)
    alterado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    alterado_em = Column(DateTime, nullable=False, server_default=func.now())
