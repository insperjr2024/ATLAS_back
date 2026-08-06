from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func
from src.database.database import Base


class DesempenhoPdiEnvioModel(Base):
    """O arquivo enviado pra um ITEM de PDI (não mais a pasta inteira — uma
    pasta pode exigir vários itens, ex: Foto + Relatório), sempre por (item,
    mentorado) — inclusive itens do PDI inicial: a diretoria sobe um arquivo
    por mentorado, não um só pra todo mundo. Reenviar no mesmo item
    substitui o arquivo anterior (ver `UploadPdiEnvioUseCase`), por isso a
    unique constraint."""

    __tablename__ = "desempenho_pdi_envio"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("desempenho_pdi_item.id"), nullable=False, index=True)
    mentorado_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    enviado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    arquivo_path = Column(String(255), nullable=False)
    arquivo_nome = Column(String(255), nullable=False)
    enviado_em = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("item_id", "mentorado_id", name="uq_pdi_envio_item_mentorado"),)
