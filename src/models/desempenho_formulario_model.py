from sqlalchemy import Column, Enum, Integer, String, Text, UniqueConstraint
from src.database.database import Base


class DesempenhoFormularioModel(Base):
    """Formulário vigente para uma combinação (tipo, papel). Só existe 1 por
    combinação — editar é atualizar esta linha e suas seções/critérios, nunca
    criar uma nova."""

    __tablename__ = "desempenho_formulario"
    __table_args__ = (UniqueConstraint("tipo", "papel", name="uq_desempenho_formulario_tipo_papel"),)

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(Enum("periodico", "finalizacao", name="desempenho_formulario_tipo"), nullable=False)
    papel = Column(Enum("consultor", "coordenador", name="desempenho_formulario_papel"), nullable=False)
    nota_geral_titulo = Column(String(200), nullable=False)
    nota_geral_descricao = Column(Text, nullable=False)
    comentarios_titulo = Column(String(200), nullable=False)
    comentarios_descricao = Column(Text, nullable=False)
    comentarios_aviso = Column(Text, nullable=False)
