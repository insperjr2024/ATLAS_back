from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.sql import func
from src.database.database import Base


class TarefaComentarioModel(Base):
    """Os comentários de uma tarefa — a conversa que acontece em cima dela.

    Quem enxerga o projeto lê e comenta: discutir uma tarefa é trabalho de
    equipe, e travar isso no autor faria o campo não servir para nada.
    Apagar o próprio comentário é do autor (e da diretoria).

    Sem edição de comentário de propósito: o valor de um fio de conversa é
    ele não mudar depois que alguém respondeu. Comentário errado se apaga e
    se escreve outro.
    """

    __tablename__ = "tarefa_comentario"

    id = Column(Integer, primary_key=True, index=True)
    tarefa_id = Column(Integer, ForeignKey("tarefa.id"), nullable=False, index=True)
    autor_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    texto = Column(Text, nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
