from sqlalchemy import Column, Date, DateTime, Enum, Integer, String
from sqlalchemy.sql import func
from src.database.database import Base


class DesempenhoPdiPastaModel(Base):
    """Uma etapa do PDI (Plano de Desenvolvimento Individual) com prazo —
    "PDI inicial" (uma por gestão, upada pela diretoria) ou "Encontro N"
    (upado pelo mentor). `tipo` decide quem tem permissão de enviar
    (`UploadPdiEnvioUseCase`), não `ordem`, que é só a ordem de exibição.
    """

    __tablename__ = "desempenho_pdi_pasta"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    tipo = Column(Enum("inicial", "encontro", name="desempenho_pdi_pasta_tipo"), nullable=False)
    prazo = Column(Date, nullable=False)
    ordem = Column(Integer, nullable=False, default=0, server_default="0")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
