"""A fase 2 prometida em `notificacao_model`: o 📌 evento do sino também vai
por e-mail, para o endereço cadastrado de quem recebeu.

**Só evento, nunca 🔄 condição.** Condição não tem instante de criação — é
recalculada a cada `GET /notificacoes` e dura enquanto o problema durar. Ela
não tem quando mandar: seria um e-mail por leitura de página, ou um resumo
diário, que é outra decisão de produto. Aqui o gatilho é o mesmo do sino: a
linha nasceu, o e-mail sai.

**A dedup do sino é a dedup do e-mail, de graça.** `registrar` só chama esta
função quando `criar_se_nao_existe` devolveu linha nova — a mesma chave que
impede o segundo aviso no sino impede o segundo e-mail. Sem isso, salvar a
equipe duas vezes mandaria dois e-mails idênticos para a mesma pessoa.

⚠ **Fora da thread da request, e falhando calado.** Duas razões, nesta ordem:

1. `registrar_varios` notifica a equipe inteira. Envio em linha faria uma
   conexão SMTP por pessoa (timeout de 15s cada) *dentro* do POST que criou o
   projeto — a tela ficaria travada esperando e-mail sair.
2. É a mesma doutrina de `registrar_notificacao`: notificar não pode derrubar
   a ação que gerou o evento. Se o SMTP estiver fora, a alocação continua
   valendo e o aviso continua no sino, que é o canal principal.

⚠ **E nunca com uma conexão de banco na mão.** O envio é uma chamada HTTP ao
Resend com timeout de 15s, e o pool do SQLAlchemy tem 5 conexões para a
instância inteira (ver `database.py`). Com as 4 threads deste pool segurando
uma sessão cada durante o envio, sobrava UMA conexão para todas as requisições
— e quem estivesse no meio de um POST tomava
`TimeoutError: QueuePool limit ... connection timed out` na primeira query
depois do `commit()`.

O estrago era exatamente o que o usuário via: `commit()` devolve a conexão ao
pool e o `refresh()` seguinte precisa pegar OUTRA. A banca (ou a tarefa)
entrava no banco e a request morria logo depois, com 500 — "deu erro, mas foi
criado". Por isso `enviar` lê o destinatário numa sessão, **fecha**, manda o
e-mail e só então abre outra para o carimbo.

O `email_enviado_em` só é carimbado depois do envio dar certo — a coluna
responde "chegou?", não "tentamos?".
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from src.config.config import get_settings
from src.database.database import SessionLocal
from src.models.notificacao_model import EMAIL_DESATIVADO_TOTAL, TIPOS_NOTIFICACAO_OPCIONAIS
from src.repositories.notificacao_repository import NotificacaoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.email import EmailSender, montar_email_notificacao

logger = logging.getLogger(__name__)

#: Poucas threads de propósito: o gargalo é o SMTP, não a CPU, e uma fila
#: curta é preferível a abrir uma thread por destinatário quando um projeto
#: com equipe grande dispara o mesmo evento para todo mundo de uma vez.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="email-notificacao")


def enfileirar(
    *,
    notificacao_id: int,
    usuario_id: int,
    tipo: str,
    titulo: str,
    corpo: Optional[str],
    rota: Optional[str],
) -> None:
    """Devolve na hora; o envio acontece numa thread do pool.

    ⚠ Recebe **valores soltos**, nunca o objeto da notificação nem a `Session`
    de quem chamou: a sessão da request é fechada assim que a resposta sai, e
    tocar num objeto ligado a ela depois disso estoura na thread de trabalho.
    Quem envia abre a própria sessão.
    """
    try:
        _executor.submit(
            enviar,
            notificacao_id=notificacao_id,
            usuario_id=usuario_id,
            tipo=tipo,
            titulo=titulo,
            corpo=corpo,
            rota=rota,
        )
    except RuntimeError:
        # Pool já encerrado (app descendo). O sino continua com o aviso.
        logger.warning("E-mail da notificação %s não enfileirado: app encerrando", notificacao_id)


def enviar(
    *,
    notificacao_id: int,
    usuario_id: int,
    tipo: str,
    titulo: str,
    corpo: Optional[str],
    rota: Optional[str],
    sender=None,
    session_factory=SessionLocal,
) -> bool:
    """Manda o e-mail e carimba `email_enviado_em`. `True` se saiu.

    `sender` e `session_factory` são injetáveis pelo mesmo motivo que
    `EmailSender` é uma classe: o teste passa um dublê à mão e a suíte não
    manda e-mail de verdade (ver a docstring de `utils/email.py`).
    """
    settings = get_settings()
    # Sem Resend configurado não há o que tentar. Silêncio, e não exceção
    # como em `EmailSender.enviar`: lá o e-mail É o fluxo (a pessoa espera um
    # link), aqui ele é a cópia de um aviso que já está no sino.
    if not settings.RESEND_API_KEY:
        return False

    try:
        # ⚠ **A sessão fecha ANTES do envio, e é essencial que feche.** Ver a
        # nota de "Fora da thread da request" no topo do módulo.
        destinatario = _destinatario(usuario_id, tipo, session_factory)
        if destinatario is None:
            return False
        nome, email = destinatario

        assunto, texto, html = montar_email_notificacao(nome, titulo, corpo, _link(rota))
        # Daqui até a volta do Resend não há conexão de banco nas mãos desta
        # thread — só o socket do e-mail.
        (sender or EmailSender()).enviar(email, assunto, texto, html)

        _carimbar_envio(notificacao_id, session_factory)
        return True
    except Exception:  # noqa: BLE001 — ver a docstring do módulo
        logger.exception(
            "Falha ao enviar e-mail da notificação %s para o usuário %s",
            notificacao_id,
            usuario_id,
        )
        return False


def _destinatario(usuario_id: int, tipo: str, session_factory) -> Optional[tuple]:
    """`(nome, email)` de quem deve receber — `None` quando não deve.

    Devolve VALORES, não o objeto do usuário: quem chama sobrevive ao
    fechamento da sessão, e tocar num objeto de sessão fechada estouraria.
    """
    db = session_factory()
    try:
        usuario = UsuarioRepository(db).get_by_id(usuario_id)
        if usuario is None:
            return None
        # Ex-membro e desligado (§10) continuam com notificações antigas no
        # banco, mas não são mais avisados por fora da plataforma.
        if not usuario.ativo:
            return None
        desativadas = usuario.notificacoes_email_desativadas or []
        # EMAIL_DESATIVADO_TOTAL desliga tudo, inclusive tipo fixo — é a
        # válvula pra conta de teste/admin com e-mail que não existe (ver
        # notificacao_model.py). Checa antes da regra normal, que só olha
        # tipo opcional.
        if EMAIL_DESATIVADO_TOTAL in desativadas:
            return None
        # Só os tipos opcionais respeitam a preferência — os de fora da lista
        # saem sempre, mesmo que o campo tenha algum lixo com o nome deles.
        if tipo in TIPOS_NOTIFICACAO_OPCIONAIS and tipo in desativadas:
            return None
        return usuario.nome, usuario.email_insper
    finally:
        db.close()


def _carimbar_envio(notificacao_id: int, session_factory) -> None:
    """Sessão nova, curta, só para o carimbo — a de leitura já foi devolvida."""
    db = session_factory()
    try:
        NotificacaoRepository(db).update(notificacao_id, email_enviado_em=datetime.now())
    finally:
        db.close()


def _link(rota: Optional[str]) -> str:
    """A rota do sino vira URL absoluta — no e-mail não existe "a página atual".

    Sem rota, cai na central: todo evento aparece lá, então o link nunca fica
    quebrado, no pior caso fica genérico.
    """
    base = get_settings().FRONTEND_URL.rstrip("/")
    if not rota:
        return f"{base}/notificacoes"
    return f"{base}/{rota.lstrip('/')}"
