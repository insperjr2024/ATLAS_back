"""O e-mail sai bem formado na rede — não só com o texto certo.

Os outros testes de e-mail conferem *conteúdo* (assunto, link, nome de quem
recebe) usando um `EmailSender` dublê, então nunca olham o que de fato viaja.
Este olha os bytes.

O bug que originou este arquivo: `EmailMessage()` sem política usa a
`email.policy.default`, que termina linha com `\n` puro e, quando o corpo tem
acento, marca a parte como `Content-Transfer-Encoding: 8bit` com os bytes
UTF-8 crus. A API do Gmail aceitava e respondia 200 — a mensagem aparecia em
"Enviados" —, mas do lado do destinatário chegava malformada e ia para o spam
ou sumia. O sintoma era cruel de ler: só chegavam os e-mails sem acento
nenhum, que por acaso caíam no caminho 7-bit.

Por isso o teste usa "Olá"/"você" de propósito: em ASCII puro ele passaria
mesmo com o bug de volta.
"""

import base64

import pytest

from src.utils.email import EmailSender, montar_email_recuperacao


class RespostaFake:
    """Dublê de `httpx.Response`: aceita tudo e devolve um access token."""

    def raise_for_status(self):
        pass

    def json(self):
        return {"access_token": "token-de-mentira"}


class SettingsFake:
    GMAIL_OAUTH_REFRESH_TOKEN = "refresh-de-mentira"
    GMAIL_OAUTH_CLIENT_ID = "id-de-mentira"
    GMAIL_OAUTH_CLIENT_SECRET = "secret-de-mentira"
    SMTP_FROM = "ATLAS <noreply.atlas1@gmail.com>"
    SMTP_USER = "noreply.atlas1@gmail.com"


@pytest.fixture
def mensagem_enviada(monkeypatch):
    """Roda o envio de verdade e devolve os bytes que iriam para o Gmail.

    Intercepta no `httpx.post` — o ponto mais externo possível — para o teste
    exercitar a montagem inteira da mensagem, que é justamente onde o bug
    estava.
    """
    import src.utils.email as modulo

    capturado = {}

    def post_fake(url, **kwargs):
        corpo = kwargs.get("json") or {}
        if "raw" in corpo:
            capturado["raw"] = corpo["raw"]
        return RespostaFake()

    monkeypatch.setattr(modulo.httpx, "post", post_fake)
    monkeypatch.setattr(modulo, "get_settings", lambda: SettingsFake())

    assunto, texto, html = montar_email_recuperacao(
        "Ana Souça", "https://atlasijr.vercel.app/redefinir-senha?token=abc", 30
    )
    EmailSender().enviar("ana@al.insper.edu.br", assunto, texto, html)

    return base64.urlsafe_b64decode(capturado["raw"])


def test_linhas_terminam_em_crlf(mensagem_enviada):
    """RFC 5322: a quebra de linha do e-mail é CRLF, não `\n`.

    Com `\n` solto, a linha de fronteira (`--boundary`) do multipart não fecha
    direito para um parser estrito e o corpo chega vazio ou truncado.
    """
    lf_solto = mensagem_enviada.count(b"\n") - mensagem_enviada.count(b"\r\n")
    assert lf_solto == 0


def test_corpo_com_acento_viaja_7bit(mensagem_enviada):
    """Nenhum byte acima de 127 na mensagem, mesmo com "Olá" e "você" nela.

    É o teste que pega a volta do bug: o acento precisa sair codificado
    (quoted-printable), não como byte cru declarado `8bit`.
    """
    assert not any(byte > 127 for byte in mensagem_enviada)
    assert b"Content-Transfer-Encoding: 8bit" not in mensagem_enviada


def test_acento_chega_legivel_do_outro_lado(mensagem_enviada):
    """Codificar não pode ser o mesmo que corromper: o texto volta inteiro.

    Sem isto, trocar o encoding por algo que só *parece* 7-bit (dropar o
    acento, por exemplo) passaria nos dois testes acima.
    """
    from email import message_from_bytes
    from email.policy import default

    msg = message_from_bytes(mensagem_enviada, policy=default)
    assert "Ana Souça" in msg.get_body(("plain",)).get_content()
    assert "Redefinição de senha - ATLAS" == msg["Subject"]


def test_mensagem_tem_data(mensagem_enviada):
    """Sem `Date`, o filtro de spam do destinatário conta ponto contra."""
    assert b"Date:" in mensagem_enviada
