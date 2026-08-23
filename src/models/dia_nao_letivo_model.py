from sqlalchemy import Column, Date, Enum, ForeignKey, Integer, String, UniqueConstraint
from src.database.database import Base


class DiaNaoLetivoModel(Base):
    """Calendário acadêmico do Insper, carregado a cada semestre.

    📐 É esta tabela que define o que é dia útil: seg–sex que NÃO está aqui.
    """

    __tablename__ = "dia_nao_letivo"
    __table_args__ = (
        UniqueConstraint(
            "semestre_id",
            "frente_id",
            "variante",
            "data",
            name="uq_dia_nao_letivo_semestre_frente_variante_data",
            # Sem isto a constraint não protegeria nada: o Postgres trata dois
            # NULLs como distintos, e `variante` é nula na maioria das linhas.
            # Ignorado fora do Postgres — o sqlite dos testes segue com a
            # unicidade frouxa, e a deduplicação de `create_dia_nao_letivo` é
            # que segura lá.
            postgresql_nulls_not_distinct=True,
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    semestre_id = Column(Integer, ForeignKey("semestre.id"), nullable=False, index=True)
    #: A frente dona deste dia. `NULL` = vale para TODAS as frentes.
    #:
    #: Cada frente abrange cursos diferentes, e cada curso tem o seu calendário
    #: acadêmico — o de Business não é o de Tech. O nulo continua existindo para
    #: o que é da faculdade inteira (feriado nacional, por exemplo) e para não
    #: invalidar a carga que já estava no banco antes desta coluna.
    frente_id = Column(Integer, ForeignKey("frente.id"), nullable=True, index=True)
    #: O calendário dentro da frente. `NULL` = vale para a frente INTEIRA.
    #:
    #: A frente foi longe até onde deu, mas ela ainda cobre vários cursos, e
    #: dentro da Tech Ciência da Computação não segue o calendário das
    #: engenharias. Aqui vai o rótulo do calendário ("Engenharias", "Ciência da
    #: Computação"), e não uma chave técnica: quem digita é a diretoria, e um
    #: mapa de código para rótulo teria de existir em dois repositórios.
    #:
    #: Só faz sentido com `frente_id` preenchido — feriado nacional não é de
    #: curso nenhum. `create_dia_nao_letivo` recusa a combinação.
    variante = Column(String(30), nullable=True)
    data = Column(Date, nullable=False, index=True)
    tipo = Column(Enum("feriado", "prova", "recesso", name="tipo_dia_nao_letivo"), nullable=False)
    descricao = Column(String(150), nullable=True)
