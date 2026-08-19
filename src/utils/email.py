"""Envio de e-mail, pela API do Resend (HTTPS).

Terceira parada desse fio: SMTP direto -> API do Gmail (conta pessoal) ->
Resend (domínio próprio, `insperjr.org`, verificado por SPF/DKIM/DMARC). A
API do Gmail resolvia o bloqueio de porta SMTP do Render, mas herdava o
limite de envio e o risco de bloqueio por volume de uma conta comum — o
Resend é infraestrutura feita para isto, sem esse teto. Fala por HTTPS
(porta 443, nunca bloqueada), então a razão original de sair do SMTP direto
continua resolvida.

**Não precisa mais montar a mensagem RFC 2822 à mão.** A API do Gmail pedia
o e-mail inteiro serializado (`raw`, base64), e dali vinha o cuidado com
`email.policy`/`cte_type="7bit"` para acento sobreviver. O Resend recebe
`subject`/`text`/`html` como campos JSON separados, em UTF-8 puro — a
codificação MIME é responsabilidade dele, não nossa.

**A classe existe para poder ser trocada por um fake no teste.** Os testes do
repo não usam `unittest.mock.patch` — escrevem dublês à mão (ver
`tests/use_cases/test_transferir_diretoria.py`). Sem essa costura, testar o
"esqueci minha senha" mandaria e-mail de verdade a cada `pytest`.
"""

from typing import Optional

import httpx

from src.config.config import get_settings
from src.utils.exceptions import RegraDeNegocioError

RESEND_SEND_URL = "https://api.resend.com/emails"


class EmailSender:
    """Envia pela API do Resend, autenticado com a API key do `.env`."""

    def enviar(self, destino: str, assunto: str, corpo_texto: str, corpo_html: str) -> None:
        settings = get_settings()

        # Falha explícita em vez de silenciosa: sem credencial configurada o
        # e-mail não sai, e o usuário ficaria esperando um link que nunca chega.
        if not settings.RESEND_API_KEY:
            raise RegraDeNegocioError(
                "Envio de e-mail não configurado no servidor (Resend API key vazia). "
                "Fale com a diretoria para redefinir sua senha."
            )

        resposta = httpx.post(
            RESEND_SEND_URL,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": settings.SMTP_FROM or settings.SMTP_USER,
                "to": [destino],
                "subject": assunto,
                # Texto puro primeiro e HTML como alternativa: cliente que não
                # renderiza HTML ainda mostra o link, em vez de um corpo vazio.
                "text": corpo_texto,
                "html": corpo_html,
            },
            timeout=15,
        )
        # `raise_for_status()` sozinho só diz o código (ex.: "403 Forbidden"),
        # não o motivo — e o motivo é o que o Resend manda no corpo ("domain
        # is not verified", "API key is restricted to a different domain"
        # etc.). Sem ele, todo 4xx cai igual no log e vira adivinhação.
        if resposta.is_error:
            raise RegraDeNegocioError(
                f"Resend recusou o envio ({resposta.status_code}): {resposta.text}"
            )


def montar_email_senha_provisoria(nome: str, senha: str, link_login: str) -> tuple[str, str, str]:
    """O e-mail de boas-vindas com a senha de primeiro acesso.

    A senha vai no CORPO, não atrás de um link, porque é assim que o fluxo foi
    pedido: a pessoa entra com ela e o próprio ATLAS a obriga a escolher outra
    antes de liberar qualquer tela. Por isso o texto diz que ela é temporária —
    quem recebe precisa saber que não vale a pena memorizá-la.

    Em `<code>` no HTML: fonte monoespaçada separa `O` de `0` na leitura, e a
    senha é feita justamente para ser lida e digitada à mão.
    """
    assunto = "Seu acesso ao ATLAS - senha provisória"

    texto = (
        f"Olá, {nome}.\n\n"
        f"A sua conta no ATLAS foi criada. Entre com esta senha provisória:\n\n"
        f"{senha}\n\n"
        f"Acesse: {link_login}\n\n"
        f"Assim que entrar, o sistema vai pedir para você escolher a SUA senha "
        f"— a provisória deixa de valer nesse momento, e até lá o resto da "
        f"plataforma fica bloqueado.\n\n"
        f"Se você não esperava este e-mail, avise a diretoria.\n"
    )

    html = (
        f"<p>Olá, {nome}.</p>"
        f"<p>A sua conta no ATLAS foi criada. Entre com esta senha provisória:</p>"
        f'<p style="font-size:18px"><code>{senha}</code></p>'
        f'<p><a href="{link_login}">Acessar o ATLAS</a></p>'
        f"<p>Assim que entrar, o sistema vai pedir para você escolher a "
        f"<strong>sua</strong> senha — a provisória deixa de valer nesse "
        f"momento, e até lá o resto da plataforma fica bloqueado.</p>"
        f"<p>Se você não esperava este e-mail, avise a diretoria.</p>"
    )

    return assunto, texto, html


def montar_email_notificacao(
    nome: str, titulo: str, corpo: Optional[str], link: str
) -> tuple[str, str, str]:
    """O espelho no e-mail de um 📌 evento do sino.

    O assunto repete o título em vez de resumir ("Você tem uma notificação"):
    é o único pedaço que aparece na lista da caixa de entrada, e quem recebe
    precisa decidir ali se abre agora ou depois — "Banca de Alfa remarcada"
    responde isso, "nova notificação" não.

    O prefixo `[ATLAS]` existe para quem quiser criar uma regra de caixa: é o
    único texto estável entre todos estes e-mails.

    ⚠ Não repete o `corpo` quando ele é vazio: boa parte dos eventos só tem
    título (`entrega_registrada`, `escalacao_banca`), e um parágrafo em branco
    no meio do e-mail parece conteúdo que se perdeu no caminho.
    """
    assunto = f"[ATLAS] {titulo}"

    detalhe_texto = f"{corpo}\n\n" if corpo else ""
    texto = (
        f"Olá, {nome}.\n\n"
        f"{titulo}\n\n"
        f"{detalhe_texto}"
        f"Ver no ATLAS: {link}\n\n"
        f"Você recebeu este e-mail porque esta notificação apareceu no seu "
        f"sino do ATLAS.\n"
    )

    detalhe_html = f"<p>{corpo}</p>" if corpo else ""
    html = (
        f"<p>Olá, {nome}.</p>"
        f"<p><strong>{titulo}</strong></p>"
        f"{detalhe_html}"
        f'<p><a href="{link}">Ver no ATLAS</a></p>'
        f"<p style=\"color:#666;font-size:12px\">Você recebeu este e-mail porque "
        f"esta notificação apareceu no seu sino do ATLAS.</p>"
    )

    return assunto, texto, html


def montar_email_recuperacao(nome: str, link: str, minutos: int) -> tuple[str, str, str]:
    """O conteúdo do e-mail de redefinição: `(assunto, texto, html)`.

    Separado do envio para o teste conferir o texto sem tocar em SMTP, e para
    quem for ajustar a redação não precisar mexer no código de rede.
    """
    assunto = "Redefinição de senha - ATLAS"

    texto = (
        f"Olá, {nome}.\n\n"
        f"Recebemos um pedido para redefinir a sua senha no ATLAS.\n"
        f"Acesse o link abaixo para escolher uma nova senha:\n\n"
        f"{link}\n\n"
        f"O link vale por {minutos} minutos e só pode ser usado uma vez.\n\n"
        f"Se não foi você que pediu, ignore este e-mail — a sua senha atual "
        f"continua valendo.\n"
    )

    html = (
        f"<p>Olá, {nome}.</p>"
        f"<p>Recebemos um pedido para redefinir a sua senha no ATLAS.</p>"
        f'<p><a href="{link}">Escolher uma nova senha</a></p>'
        f"<p>O link vale por {minutos} minutos e só pode ser usado uma vez.</p>"
        f"<p>Se não foi você que pediu, ignore este e-mail — a sua senha atual "
        f"continua valendo.</p>"
    )

    return assunto, texto, html
