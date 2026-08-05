"""Envio de e-mail, via `smtplib` da biblioteca padrão.

Sem dependência nova de propósito: o README manda manter `pyproject.toml` e
`requirements.txt` em sincronia a cada pacote instalado, e a stdlib resolve o
que precisamos (um e-mail transacional, texto e HTML).

**A classe existe para poder ser trocada por um fake no teste.** Os testes do
repo não usam `unittest.mock.patch` — escrevem dublês à mão (ver
`tests/use_cases/test_transferir_diretoria.py`). Sem essa costura, testar o
"esqueci minha senha" mandaria e-mail de verdade a cada `pytest`.
"""

import smtplib
from email.message import EmailMessage

from src.config.config import get_settings
from src.utils.exceptions import RegraDeNegocioError


class EmailSender:
    """Envia pelo SMTP configurado no `.env`."""

    def enviar(self, destino: str, assunto: str, corpo_texto: str, corpo_html: str) -> None:
        settings = get_settings()

        # Falha explícita em vez de silenciosa: sem host configurado o e-mail
        # não sai, e o usuário ficaria esperando um link que nunca chega.
        if not settings.SMTP_HOST:
            raise RegraDeNegocioError(
                "Envio de e-mail não configurado no servidor (SMTP_HOST vazio). "
                "Fale com a diretoria para redefinir sua senha."
            )

        mensagem = EmailMessage()
        mensagem["Subject"] = assunto
        mensagem["From"] = settings.SMTP_FROM or settings.SMTP_USER
        mensagem["To"] = destino
        # O texto puro vem primeiro e o HTML como alternativa: cliente que não
        # renderiza HTML ainda mostra o link, em vez de um corpo vazio.
        mensagem.set_content(corpo_texto)
        mensagem.add_alternative(corpo_html, subtype="html")

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(mensagem)


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
