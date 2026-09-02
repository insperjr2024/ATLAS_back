from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from src.database.database import Base


class ProjetoModel(Base):
    """O cadastro do §6.3. `data_kickoff` nasce vazia — o kickoff ainda não
    existe no registro (§5.1); vazio = alerta de kickoff pendente."""

    __tablename__ = "projeto"

    id = Column(Integer, primary_key=True, index=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
    nome = Column(String(150), nullable=False)
    #: Único campo do cadastro (§6.3) que não é obrigatório — nem todo
    #: projeto tem um cliente externo definido já na criação.
    cliente = Column(String(150), nullable=True)
    descricao = Column(Text, nullable=True)
    link_proposta = Column(String(255), nullable=True)
    # A proposta é ou um link, ou um PDF anexado, nunca os dois (ver
    # UploadAnexoPropostaUseCase, que zera link_proposta ao receber o anexo).
    #
    # O conteúdo do PDF fica no PRÓPRIO banco, não em disco: o disco do
    # servidor de deploy é efêmero e some a cada redeploy/restart, e um arquivo
    # gravado lá desaparecia sem deixar rastro. Mesma escolha do envio de PDI
    # (ver `DesempenhoPdiEnvioModel`).
    anexo_proposta_conteudo = Column(LargeBinary, nullable=True)
    anexo_proposta_nome = Column(String(255), nullable=True)
    status = Column(
        Enum(
            "vendido",
            "ambientacao",
            "em_andamento",
            "validacao_bancas",
            "envio_tep",
            "periodo_ajustes",
            "finalizado",
            "pausado",
            name="status_projeto",
        ),
        nullable=False,
        default="vendido",
        server_default="vendido",
    )
    dias_ambientacao = Column(Integer, nullable=False, default=5, server_default="5")
    #: Teto de consultores do projeto — o que decide se ele ainda tem vaga na
    #: tela de declaração de interesse. Não conta o coordenador: ele entra pelo
    #: papel, não por vaga.
    max_consultores = Column(Integer, nullable=False, default=3, server_default="3")
    data_kickoff = Column(Date, nullable=True)
    #: ⭐ Quando NÃO nulo, substitui `data_kickoff` como início da janela de
    #: ambientação (ver `utils/ambientacao.py`). `None` (o padrão) é o caso
    #: normal: ambientação começa no kickoff, sem exceção.
    #:
    #: Existe só pro caso em que a ambientação, na prática, começou antes do
    #: kickoff (ex.: o time já estava em campo e o kickoff formal atrasou) —
    #: o coordenador do projeto corrige aqui. Editável só para ANTECIPAR: a
    #: validação (`UpdateInicioAmbientacaoUseCase`) exige
    #: `data_inicio_ambientacao <= data_kickoff`, e não mais que
    #: `dias_ambientacao` dias úteis antes dele — o kickoff nunca fica fora
    #: da própria janela de ambientação que ele mesmo abriu.
    data_inicio_ambientacao = Column(Date, nullable=True)
    # ⚠ `calendario` saiu daqui na `e5c1a9f37b64`. O calendário acadêmico é a
    # base de contagem de um ESCOPO (`projeto_escopo.calendario`), não do
    # projeto: um projeto sinérgico tem escopos em frentes diferentes, cada uma
    # com o calendário do curso dela, e um campo só não representa os dois.
    #: ⚠ **Não é lida em lugar nenhum desde a reformulação do cronograma.**
    #: "Entrega ao cliente" virou DERIVADA — é a do último escopo entregue
    #: (ver `serializar_projeto_completo`). A coluna fica porque apagá-la
    #: exigiria migration destrutiva num campo que ainda pode ter dado
    #: histórico; nada escreve nela.
    data_entrega_cliente = Column(Date, nullable=True)
    #: ⭐ A PROMESSA feita ao cliente na venda — a data combinada, definida já
    #: na criação do projeto.
    #:
    #: ⚠ **Outra coisa que `data_entrega_cliente`**, e é justamente por isso
    #: que é uma coluna nova em vez de reaproveitar aquela. São duas perguntas
    #: diferentes sobre a mesma promessa:
    #:
    #: - esta é o que foi PROMETIDO, e não muda quando o trabalho anda;
    #: - a derivada é o que ACONTECEU (a entrega do último escopo).
    #:
    #: Guardá-las no mesmo campo foi o bug que fez a coluna acima ser
    #: aposentada: a promessa era sobrescrita pela realidade no primeiro
    #: reagendamento, e ninguém mais sabia se a data na tela era combinado ou
    #: fato consumado. Separadas, dá para responder "entregamos no prazo?" no
    #: nível do PROJETO — hoje isso só existe por escopo.
    data_entrega_prevista_cliente = Column(Date, nullable=True)
    dia_reuniao_padrao = Column(Integer, nullable=True)  # 1=seg ... 7=dom
    # Nullable: se a pessoa que criou for excluída de vez (usuário desligado,
    # ver DeleteUsuarioPermanenteUseCase), o projeto sobrevive — só "quem
    # criou" vira desconhecido, o time e o trabalho continuam intactos.
    criado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
    # Preserva o status de antes de pausar, para o retomar voltar ao lugar certo
    # sem precisar reconsultar o histórico toda vez.
    status_antes_pausa = Column(String(30), nullable=True)
    # Arquivar não é excluir: some das listagens normais, mas nada é apagado
    # — banca, avaliação e histórico continuam intactos (ver ArquivarProjetoUseCase).
    arquivado_em = Column(DateTime, nullable=True)
    # "Limpar histórico" também não apaga nada: as linhas de
    # `projeto_status_historico` anteriores a este corte só saem da timeline
    # (§4). Continuam no banco intactas porque alimentam a contagem de dias
    # (§5.4) — apagá-las de verdade mudaria retroativamente esse cálculo.
    # `None` = nada oculto, mostra a timeline inteira.
    historico_oculto_ate = Column(DateTime, nullable=True)
