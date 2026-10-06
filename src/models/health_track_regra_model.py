from sqlalchemy import Column, DateTime, ForeignKey, Integer
from src.database.database import Base


class HealthTrackRegraModel(Base):
    """Os parâmetros que transformam as cores dos pilares no status geral do
    projeto (Health Track §5), editáveis pela diretoria de projetos.

    **Cada edição é uma versão nova, nunca uma alteração.** O status de um
    ciclo é mostrado pela regra que valia na data dele E pela regra atual
    (`utils/health_track_status.py`) — sem as versões antigas, a primeira
    leitura deixaria de existir na primeira edição.

    Amarelo não tem parâmetros: é o que não é vermelho nem verde. Ver o
    docstring de `utils/health_track_status.py`.
    """

    __tablename__ = "health_track_regra"

    id = Column(Integer, primary_key=True, index=True)
    verde_max_amarelos = Column(Integer, nullable=False)
    verde_max_vermelhos = Column(Integer, nullable=False)
    #: Vermelho: basta atingir UM dos dois mínimos.
    vermelho_min_amarelos = Column(Integer, nullable=False)
    vermelho_min_vermelhos = Column(Integer, nullable=False)
    #: A partir de quando esta versão vale. A inicial nasce no passado, para
    #: cobrir todo ciclo já preenchido.
    vigente_desde = Column(DateTime, nullable=False, index=True)
    #: Vazio na regra inicial, que veio da migration.
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
