from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from src.database.database import Base


class BancaModel(Base):
    """A banca de um escopo (§5.5, §8).

    F5 costurou esta tabela ao projeto. Três cuidados que valem registro:

    - `projeto_escopo_id` é a ligação real com o projeto, e é **nullable**
      porque as bancas legadas do módulo antigo não têm escopo vendido. É
      UNIQUE: um escopo tem no máximo uma banca ("uma data só" — marcar pelo
      cronograma escreve NESTA linha, sem espelho nem sincronização).
    - `data_hora` voltou a ser nullable: sem isso o estado `nao_marcada` seria
      inalcançável.
    - `escopo_id` (o catálogo) virou nullable porque um escopo "Outro" não tem
      linha de catálogo — e §5.5 diz que todo escopo tem banca.
    """

    __tablename__ = "banca"
    __table_args__ = (
        UniqueConstraint("projeto_escopo_id", name="uq_banca_projeto_escopo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nome_projeto = Column(String(150), nullable=False)
    escopo_id = Column(Integer, ForeignKey("escopo.id"), nullable=True)
    coordenador_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    data_hora = Column(DateTime, nullable=True)

    projeto_escopo_id = Column(
        Integer, ForeignKey("projeto_escopo.id"), nullable=True, index=True
    )
    #: ⭐ A fonte da verdade do "aconteceu". Sem isto, banca com data passada
    #: era reportada como realizada só pelo relógio — e "venceu e não
    #: aconteceu" não existia no sistema.
    realizado_em = Column(DateTime, nullable=True)
    #: 🔒 Libera ou trava a entrega ao cliente (§5.5, §8).
    resultado = Column(
        Enum("aprovada", "nao_aprovada", name="resultado_banca"), nullable=True
    )
    #: Choque de horário só é liberado pela diretoria (§8).
    excecao_choque_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    excecao_choque_nota = Column(String(255), nullable=True)
    #: Nulo = usa a soma do `piso_banca` das frentes vinculadas (§8). Só a
    #: diretoria define isto, para bancas cuja gestão precisa de mais gente
    #: que o padrão da(s) frente(s).
    piso_minimo_override = Column(Integer, nullable=True)
