from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func
from src.database.database import Base


class ProjetoJustificativaAtrasoModel(Base):
    """A nota da diretoria pro atraso de um projeto (§7.4).

    O alerta de atraso é automático — ninguém digita nada pra ele acontecer.
    O "porquê" é outra coisa: a diretoria pergunta ao coordenador e registra
    aqui, e fica gravado no histórico do projeto pra sempre (não é campo
    editável, é registro — uma nota nova não apaga a anterior).
    """

    __tablename__ = "projeto_justificativa_atraso"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    #: Qual escopo motivou a nota, quando dá pra apontar um só — None quando a
    #: diretoria está registrando sobre o atraso do projeto como um todo.
    projeto_escopo_id = Column(Integer, ForeignKey("projeto_escopo.id"), nullable=True)
    #: "banca" | "entrega_interna" | "entrega_externa" — igual ao `tipo` de
    #: `MotivoAtraso` (`src/utils/atraso_monitoramento.py`). Precisa disto além
    #: do escopo porque o MESMO escopo pode estar atrasado em banca E entrega
    #: ao mesmo tempo — só o escopo não diz qual dos dois foi respondido.
    #: None = nota geral do projeto, cobre qualquer motivo aberto.
    tipo = Column(String(30), nullable=True)
    texto = Column(Text, nullable=False)
    registrado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    registrado_em = Column(DateTime, nullable=False, server_default=func.now())
