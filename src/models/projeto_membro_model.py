from sqlalchemy import Column, Date, Enum, ForeignKey, Integer
from src.database.database import Base


class ProjetoMembroModel(Base):
    """Equipe COM histórico — a substituta do `equipe_projeto` legado.

    Trocar alguém = preencher `saiu_em` da linha antiga e criar outra, nunca
    sobrescrever. Equipe atual = linhas com `saiu_em` vazio. É daqui que sai o
    bloqueio do §8 ("a equipe do próprio projeto não se inscreve na sua
    banca"): banca → projeto_escopo → projeto → projeto_membro.
    """

    __tablename__ = "projeto_membro"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    papel = Column(Enum("coordenador", "consultor", name="papel_projeto_membro"), nullable=False)
    entrou_em = Column(Date, nullable=False)
    saiu_em = Column(Date, nullable=True)
