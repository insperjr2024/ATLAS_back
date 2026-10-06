from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, Text
from src.database.database import Base

#: As três classificações de um pilar (Health Track §3), com o texto da spec
#: — é o que a tela mostra a quem escolhe a cor. Diferente dos pilares, a
#: spec não as torna editáveis, então ficam aqui e não numa tabela.
CLASSIFICACOES_HEALTH_TRACK = (
    {
        "cor": "verde",
        "nome": "Saudável",
        "descricao": "O pilar está dentro do esperado e não demanda intervenção.",
    },
    {
        "cor": "amarelo",
        "nome": "Atenção",
        "descricao": "Existe um risco ou desvio relevante, mas ainda controlável.",
    },
    {
        "cor": "vermelho",
        "nome": "Crítico",
        "descricao": (
            "Existe um problema relevante que já está impactando ou possui alta "
            "probabilidade de impactar o projeto."
        ),
    },
)

#: Derivado da lista acima — uma cor nova entra num lugar só.
CORES_HEALTH_TRACK = tuple(c["cor"] for c in CLASSIFICACOES_HEALTH_TRACK)


class HealthTrackAvaliacaoModel(Base):
    """A cor de UM pilar de UM projeto num momento (Health Track §3).

    **Só se insere, nunca se altera.** Reavaliar um pilar é uma linha nova;
    a anterior fica como estava. É o histórico projeto + pilar + data que a
    persistência ("amarelo há 2 ciclos", §7) e a evolução (§16) vão ler.

    Um preenchimento grava uma linha por pilar ativo, todas com o MESMO
    `avaliado_em` — é isso que identifica o ciclo, sem tabela de cabeçalho.
    """

    __tablename__ = "health_track_avaliacao"
    __table_args__ = (
        # O caminho das duas leituras: última cor de cada pilar e histórico.
        Index("ix_health_track_avaliacao_projeto_pilar_data", "projeto_id", "pilar_id", "avaliado_em"),
    )

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=False, index=True)
    pilar_id = Column(Integer, ForeignKey("health_track_pilar.id"), nullable=False, index=True)
    cor = Column(Enum(*CORES_HEALTH_TRACK, name="cor_health_track"), nullable=False)
    comentario = Column(Text, nullable=True)
    avaliado_por = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    avaliado_em = Column(DateTime, nullable=False)
