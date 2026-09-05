from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from src.database.database import Base

TIPO_NOTIFICACAO_ENUM = Enum(
    # 📌 eventos da PLATAFORMA (§6.6) — gravados no ato pelo use case
    "alocado_em_projeto",
    #: Declaração de interesse: avisa o coordenador que alguém quer entrar, e
    #: depois o solicitante do que foi decidido.
    "solicitacao_projeto",
    "entrega_registrada",
    #: O plano mudou depois de combinado — §5.6 (banca) e a data prometida ao
    #: cliente. Os dois nunca são silenciosos.
    "banca_remarcada",
    "entrega_alterada",
    #: §7.4: a diretoria PERGUNTOU ao coordenador por que o escopo atrasou. O
    #: case descreve essa pergunta ("ela pergunta ao coordenador e digita a
    #: nota"); só a segunda metade existia na plataforma.
    "justificativa_pedida",
    # 📌 eventos de BANCAS (§8) — entram por `utils/notificar.py`
    "escalacao_banca",
    "troca_banca",
    "avaliacao_pendente",
    "banca_aviso",
    #: 📌 Pedido de dias de ajuste (§8) — o coordenador pede, a diretoria
    #: responde. ⚠ Estavam no BANCO e em uso, e faltavam nesta lista: quem
    #: escrevesse um ALTER de ENUM a partir daqui truncaria as linhas já
    #: gravadas com eles.
    "reajuste_solicitado",
    "reajuste_respondido",
    #: 📌 Avaliação de Desempenho (Prioridade 2) — não é de projeto: o
    #: destinatário é quem tem o que responder, venha do projeto que vier.
    "lote_desempenho_aberto",
    #: ⚠ Faltava também no Postgres — ver a migration `a2c8f61de930`, que
    #: fecha o mesmo buraco de `e4b1d7c9a052` (Enum do model não é Enum do
    #: banco em Postgres; sem a migration, o INSERT falha e o lembrete de
    #: 24h nunca sairia).
    "lote_desempenho_lembrete",
    #: A banca que abriu este lote sozinha foi cancelada DEPOIS de já
    #: realizada — o lote é desfeito e quem tinha o que responder é avisado.
    "lote_desempenho_cancelado",
    #: 📌 PDI (relatório de mentoria) — mesmo motivo: destinatário é o
    #: mentor (ou a diretoria), não quem "enxerga o projeto".
    "pdi_prazo_proximo",
    "pdi_prazo_vencido",
    # 🔄 condições — calculadas na leitura; a linha só nasce ao marcar como lida
    "kickoff_pendente",
    "tarefa_vencida",
    # Voltaram com o fluxo de reajuste (a main os removera junto com ele).
    "reajuste_solicitado",
    "reajuste_respondido",
    # ⚠ Emitido por `marcar_banca_escopo` desde o commit 3035559, mas nunca
    # declarado aqui — a coluna é ENUM, então o INSERT vinha com "Data
    # truncated for column 'tipo'" e derrubava o registro de realização da
    # banca inteiro. O evento é real e útil; o que faltava era a declaração.
    "descricao_coordenador_pendente",
    "banca_nao_marcada",
    "projeto_sem_reuniao",
    "banca_hoje",
    name="tipo_notificacao",
)

ORIGEM_NOTIFICACAO_ENUM = Enum("evento", "condicao", name="origem_notificacao")

#: Os únicos tipos que a pessoa pode desligar do e-mail
#: (`usuario.notificacoes_email_desativadas`). Os de fora desta lista saem
#: sempre — decisão de 2026-08-17: são pedido direto de alguém (
#: `justificativa_pedida`, `solicitacao_projeto`), prazo com bloqueio
#: depois que vence (`avaliacao_pendente`, `pdi_prazo_proximo`,
#: `pdi_prazo_vencido`, `lote_desempenho_aberto`), compromisso de agenda
#: que mudou (`banca_remarcada`, `banca_hoje`), fluxo de aprovação (
#: `reajuste_solicitado`, `reajuste_respondido`), tarefa obrigatória (
#: `descricao_coordenador_pendente`) ou vencimento que é do dono da tarefa
#: resolver (`tarefa_vencida`).
TIPOS_NOTIFICACAO_OPCIONAIS = frozenset(
    {
        "alocado_em_projeto",
        "entrega_registrada",
        "escalacao_banca",
        "troca_banca",
        "banca_aviso",
        "entrega_alterada",
        "kickoff_pendente",
        "banca_nao_marcada",
        "projeto_sem_reuniao",
    }
)

#: Valor especial de `notificacoes_email_desativadas` que desliga TODO tipo,
#: inclusive os fixos da lista acima — não é um tipo de verdade, é a válvula
#: pra conta de teste/admin com e-mail que não existe (ex.: `admin@
#: insperjr.com`) parar de gastar cota do Resend e de acumular bounce à toa.
#: Continua no sino normalmente; só o e-mail é que some.
EMAIL_DESATIVADO_TOTAL = "__tudo__"


class NotificacaoModel(Base):
    """A central de notificações do §6.6 e do §8, numa tabela só.

    ⚠ **Nem toda notificação é uma linha aqui, e essa é a ideia central.**

    Os alertas se dividem em dois, e tratá-los igual é o erro caro:

    - **📌 evento** ("você foi alocado no Alfa", "você foi escalado para a
      banca") aconteceu num instante e não é recalculável depois — ninguém
      sabe quando você entrou no projeto se não gravar. Vira linha na hora,
      dentro do use case.
    - **🔄 condição** ("o Alfa está sem kickoff") é um estado que dura
      enquanto o problema durar, e é derivável a qualquer momento de
      `projeto.data_kickoff`. **Não vira linha.** É recalculada a cada
      `GET /notificacoes` por `utils/condicoes_alerta.py`.

    Gravar as condições exigiria dois jobs: um para criar a linha e outro para
    apagá-la quando o problema fosse resolvido. Sem o segundo, o consultor
    conclui a tarefa às 10h e o sino continua cobrando até o dia seguinte.
    Calcular na leitura resolve os dois de graça — e é o mesmo princípio que
    `tarefa_status.eh_vencida` já aplica ("🧮 sempre calculado, nunca gravado").

    Consequência: linhas com `origem="condicao"` existem **só** para guardar o
    `lida_em`. A linha não é a notificação; é o registro de que ela já foi
    vista. É por isso que o alerta some sozinho quando o problema é resolvido,
    mesmo que a linha de "lida" continue no banco.

    📌 **Sobre a fusão com a versão de bancas.** Esta tabela nasceu simples
    (`mensagem` + `banca_id` + `lida`) para o push automático e a troca do §8.
    Ao juntar com os alertas do §6.6 os campos viraram: `mensagem`→`titulo`,
    `lida`→`lida_em` (o timestamp responde "quando", que o booleano não
    respondia) e `banca_id`→`payload["banca_id"]` — uma FK só para bancas
    obrigaria uma coluna nova a cada domínio que passasse a notificar. Os
    gatilhos de banca não mudaram de lugar: `utils/notificar.py` continua
    sendo a porta deles, agora escrevendo neste formato.

    `email_enviado_em` é carimbado por `enviar_email_notificacao` quando o
    espelho do evento sai por e-mail. Continua nulo em duas situações
    legítimas, e as duas são esperadas: linha de `origem="condicao"` (que não
    é notificação, é marcação de leitura) e evento cujo envio falhou ou não
    tinha SMTP configurado — a coluna responde "chegou?", não "tentamos?".
    """

    __tablename__ = "notificacao"
    __table_args__ = (
        # O anti-spam do §6.6. `chave_dedup` carrega a janela quando ela
        # importa (`projeto_sem_reuniao:projeto=1:semana=2026-W32`), então a
        # semana seguinte gera chave nova e o alerta volta — que é o certo.
        UniqueConstraint("usuario_id", "chave_dedup", name="uq_notificacao_usuario_chave"),
    )

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer, ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo = Column(TIPO_NOTIFICACAO_ENUM, nullable=False)
    origem = Column(ORIGEM_NOTIFICACAO_ENUM, nullable=False)
    titulo = Column(String(255), nullable=False)
    corpo = Column(String(500), nullable=True)
    #: Para abrir direto na rota do problema. Nulo em alerta que não é de
    #: projeto — banca, por exemplo, que o §8 proíbe a equipe de assistir.
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=True, index=True)
    #: Referências extras — `banca_id`, `tarefa_id`, `projeto_escopo_id`, `rota`.
    payload = Column(JSON, nullable=True)
    chave_dedup = Column(String(120), nullable=False)
    lida_em = Column(DateTime, nullable=True)
    #: 🔮 Fase 2. Nulo hoje em todas as linhas.
    email_enviado_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
