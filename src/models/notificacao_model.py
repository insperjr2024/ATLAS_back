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
    # 📌 eventos — gravados no ato pelo use case
    "alocado_em_projeto",
    "escalacao_banca",
    "entrega_registrada",
    # 🔄 condições — calculadas na leitura; a linha só nasce ao marcar como lida
    "kickoff_pendente",
    "tarefa_vencida",
    "banca_nao_marcada",
    "projeto_sem_reuniao",
    "banca_hoje",
    name="tipo_notificacao",
)

ORIGEM_NOTIFICACAO_ENUM = Enum("evento", "condicao", name="origem_notificacao")


class NotificacaoModel(Base):
    """A central de notificações do §6.6 — hoje só no app.

    ⚠ **Nem toda notificação é uma linha aqui, e essa é a ideia central.**

    Os alertas se dividem em dois, e tratá-los igual é o erro caro:

    - **📌 evento** ("você foi alocado no Alfa") aconteceu num instante e não
      é recalculável depois — ninguém sabe quando você entrou no projeto se
      não gravar. Vira linha na hora, dentro do use case.
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

    `email_enviado_em` nasce sempre nulo: o canal de e-mail é a fase 2. A
    coluna existe agora para que ela seja um job preenchendo um campo, não uma
    segunda migration.
    """

    __tablename__ = "notificacao"
    __table_args__ = (
        # O anti-spam do §6.6. `chave_dedup` carrega a janela quando ela
        # importa (`sem_reuniao:projeto=1:semana=2026-W32`), então a semana
        # seguinte gera chave nova e o alerta volta — que é o certo.
        UniqueConstraint("usuario_id", "chave_dedup", name="uq_notificacao_usuario_chave"),
    )

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    tipo = Column(TIPO_NOTIFICACAO_ENUM, nullable=False)
    origem = Column(ORIGEM_NOTIFICACAO_ENUM, nullable=False)
    titulo = Column(String(200), nullable=False)
    corpo = Column(String(500), nullable=True)
    #: Para abrir direto na rota do problema. Nulo em alerta que não é de
    #: projeto (escalação em banca, por exemplo).
    projeto_id = Column(Integer, ForeignKey("projeto.id"), nullable=True, index=True)
    #: Referências extras — `tarefa_id`, `banca_id`, `projeto_escopo_id`.
    payload = Column(JSON, nullable=True)
    chave_dedup = Column(String(120), nullable=False)
    lida_em = Column(DateTime, nullable=True)
    #: 🔮 Fase 2. Nulo hoje em todas as linhas.
    email_enviado_em = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, nullable=False, server_default=func.now())
