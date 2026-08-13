from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey
from src.database.database import Base


class AvaliacaoModel(Base):
    """Uma submissão do formulário de avaliação de bancas.

    Os 4 campos abaixo são o Bloco 1 ("Informações iniciais") do formulário
    padrão — texto livre (`nome_avaliador`, `projeto_avaliado`), escolha
    única (`tipo_avaliador`) e o escopo que o próprio avaliador confirma
    estar avaliando (`escopo_avaliado_id`/`escopo_avaliado_outro`, pro caso
    "Outro"). Repetem informação que o sistema já tem (banca, avaliador
    logado), mas o formulário pede de novo por padrão — e é essa resposta,
    não `banca.escopo_id`, que decide qual bloco técnico (§ pergunta.escopo_id)
    aparece: o avaliador pode confirmar um escopo diferente do cadastrado.
    """

    __tablename__ = "avaliacao"

    id = Column(Integer, primary_key=True, index=True)
    banca_id = Column(Integer, ForeignKey("banca.id", ondelete="CASCADE"), nullable=False)
    avaliador_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    formulario_id = Column(Integer, ForeignKey("formulario.id"), nullable=False)
    status = Column(String(20), nullable=False, default="rascunho")
    #: ⭐ O VOTO de quem assistiu: esta banca aprova o trabalho?
    #:
    #: É daqui que sai `banca.resultado` — por MAIORIA dos votos submetidos, e
    #: não da caneta de uma pessoa (ver `utils/apuracao_banca.py`). As notas
    #: por critério continuam existindo e medem outra coisa: elas dão a nota
    #: final do projeto; o voto decide se o trabalho pode ir ao cliente.
    #:
    #: ⚠ **Nullable, e tem de ser.** Rascunho ainda não votou, e as avaliações
    #: gravadas antes desta coluna existir não têm voto nenhum. A
    #: obrigatoriedade é da SUBMISSÃO, cobrada no use case — pôr `NOT NULL`
    #: aqui exigiria inventar um voto para o passado.
    voto_aprovacao = Column(Boolean, nullable=True)
    #: ⭐ Em QUAL tentativa da banca este voto foi dado (§9).
    #:
    #: ⚠ Sem isto, os votos da 1ª banca contariam na apuração da 2ª — que é
    #: exatamente a sessão que existe para dar ao escopo uma chance nova.
    #: `avaliacao.banca_id` sozinho não distingue tentativa, porque a linha de
    #: `banca` é a mesma nas duas.
    #:
    #: Integer e não FK para `banca_sessao.id`: o backfill vira um DEFAULT puro
    #: (toda avaliação existente é da sessão 1) e a apuração filtra com
    #: comparação de inteiro, sem join.
    sessao = Column(Integer, nullable=False, default=1, server_default="1")
    comentario_feedback = Column(String(1000), nullable=True)
    submetida_em = Column(DateTime, nullable=True)
    nome_avaliador = Column(String(150), nullable=True)
    #: "consultor" ou "lideranca" — a resposta livre da pergunta, não o
    #: `usuario.posicao` (que distingue 4 posições, não 2).
    tipo_avaliador = Column(String(20), nullable=True)
    projeto_avaliado = Column(String(150), nullable=True)
    escopo_avaliado_id = Column(Integer, ForeignKey("escopo.id"), nullable=True)
    #: Preenchido só quando `escopo_avaliado_id` é nulo (a opção "Outro").
    escopo_avaliado_outro = Column(String(150), nullable=True)