from sqlalchemy import Boolean, Column, Integer, String
from src.database.database import Base


class FrenteModel(Base):
    """As 4 frentes de execução (§2).

    `piso_banca` é o mínimo de membros da própria frente que a banca exige
    (§8: Business 3 · Tech 2 · Eng. de Processos 2 · Direito 1) — antes disso
    só existia um teto global em `configuracao.vagas_por_banca`.
    """

    __tablename__ = "frente"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(50), nullable=False)
    ativa = Column(Boolean, nullable=False, default=True, server_default="1")
    piso_banca = Column(Integer, nullable=False, default=1, server_default="1")
    #: Qual calendário da frente vale para um projeto que não escolheu o dele.
    #:
    #: `NULL` = a frente tem um calendário só, o de `dia_nao_letivo.variante`
    #: nulo. É o caso de Business, Processos e Direito. A Tech aponta para
    #: "Engenharias", que é o que a maioria dos cursos dela segue.
    calendario_padrao = Column(String(30), nullable=True)