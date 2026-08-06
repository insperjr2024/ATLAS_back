from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
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