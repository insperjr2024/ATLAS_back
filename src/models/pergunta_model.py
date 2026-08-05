from sqlalchemy import Column, Integer, String, ForeignKey
from src.database.database import Base


class PerguntaModel(Base):
    """Uma pergunta do formulário de avaliação.

    `escopo_id` nulo = pergunta universal (aparece em toda banca, qualquer
    escopo — os blocos "Informações iniciais" e "Avaliação final"). Com
    valor, a pergunta só aparece quando a banca avaliada é daquele escopo —
    é o que faz o Bloco 2 (critérios técnicos) variar por tipo de entrega.
    """

    __tablename__ = "pergunta"

    id = Column(Integer, primary_key=True, index=True)
    formulario_id = Column(Integer, ForeignKey("formulario.id"), nullable=False)
    texto = Column(String(500), nullable=False)
    ordem = Column(Integer, nullable=False)
    tipo_resposta = Column(String(20), nullable=False, default="nota")
    escopo_id = Column(Integer, ForeignKey("escopo.id"), nullable=True, index=True)