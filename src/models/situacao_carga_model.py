from sqlalchemy import Column, Enum, Integer, String, UniqueConstraint
from src.database.database import Base


class SituacaoCargaModel(Base):
    """Os estados de carga da aba de Alocação (§7.3), definidos pela diretoria.

    Não é um limite único: é uma escala. A diretoria descreve, por papel, o que
    cada quantidade de projetos significa — por exemplo, para consultor:

        0 a 1 projetos ... "Disponível"
        2 projetos ....... "Quantidade ideal"
        3 ou mais ........ "Carga alta"

    Configurável porque o ponto de saturação muda: uma frente com 4 pessoas e
    outra com 15 não têm o mesmo "ideal", e isso varia a cada gestão.

    ⭐ **Guarda só o mínimo, não a faixa.** Cada situação vale de `min_projetos`
    até o mínimo da próxima, menos um. Isso torna buraco e sobreposição
    *impossíveis de configurar* — com `min` e `max` livres, a diretoria poderia
    criar "0 a 1" e "3 ou mais" e deixar quem tem 2 projetos sem situação
    nenhuma, e a tela teria de inventar um fallback.

    ⭐ **São sempre três faixas por papel**, e não um número livre: não há criar
    nem excluir, só editar. Com quantidade livre, uma escala sem nenhuma faixa
    alta deixaria o card de demanda alta da aba de Alocação vazio para sempre,
    sem nada na tela explicando por quê — configuração quebrada em silêncio.
    Fixando três, a faixa mais alta existe por construção.

    A escala NÃO precisa começar em zero — o mínimo da primeira faixa é
    editável. Subi-lo para 2 significa "abaixo disso não rotulo nada", e quem
    ficar fora de qualquer faixa vem sem situação; a tela mostra um travessão,
    que é a resposta honesta.
    """

    __tablename__ = "situacao_carga"
    __table_args__ = (
        # Duas situações com o mesmo mínimo no mesmo papel tornariam a
        # resolução ambígua — qual das duas vale para aquele número?
        UniqueConstraint("papel", "min_projetos", name="uq_situacao_papel_minimo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    papel = Column(
        Enum("coordenador", "consultor", name="papel_situacao_carga"),
        nullable=False,
        index=True,
    )
    nome = Column(String(60), nullable=False)
    #: A partir de quantos projetos ativos esta situação vale.
    min_projetos = Column(Integer, nullable=False)
    #: Qual pílula a tela usa. Escolha FECHADA (ok / atencao / alerta / neutro),
    #: e não cor livre: a rampa de cor do monitoramento carrega significado de
    #: gravidade, e cor arbitrária quebraria essa leitura além de escapar do
    #: contraste mínimo já verificado.
    #:
    #: É só cor. Quem entra no card de demanda alta sai da POSIÇÃO na escala
    #: (a faixa de maior mínimo), não daqui — assim trocar as cores nunca
    #: esvazia o card.
    tom = Column(
        Enum("ok", "atencao", "alerta", "neutro", name="tom_situacao_carga"),
        nullable=False,
        default="neutro",
        server_default="neutro",
    )
