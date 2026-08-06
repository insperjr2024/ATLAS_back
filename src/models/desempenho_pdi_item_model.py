from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.sql import func
from src.database.database import Base


class DesempenhoPdiItemModel(Base):
    """Um documento exigido dentro de uma pasta de PDI — a pasta vira uma
    checklist (ex: "Encontro 1" pode exigir uma Foto E um Relatório, cada um
    com seu próprio envio, ver `DesempenhoPdiEnvioModel`). `tipo_arquivo`
    restringe o formato aceito no upload desse item (`validar_arquivo_pdi`).
    """

    __tablename__ = "desempenho_pdi_item"

    id = Column(Integer, primary_key=True, index=True)
    pasta_id = Column(Integer, ForeignKey("desempenho_pdi_pasta.id"), nullable=False, index=True)
    nome = Column(String(150), nullable=False)
    tipo_arquivo = Column(
        Enum("documento", "foto", "qualquer", name="desempenho_pdi_item_tipo_arquivo"),
        nullable=False,
        default="qualquer",
        server_default="qualquer",
    )
    ordem = Column(Integer, nullable=False, default=0, server_default="0")
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
