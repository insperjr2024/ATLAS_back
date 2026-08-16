"""Confere se o Gmail OAuth do `.env` está mandando e-mail de verdade.

    uv run python -m scripts.testar_email seu.email@al.insper.edu.br

Manda o MESMO e-mail de boas-vindas do cadastro, com uma senha falsa e bem
marcada — é o que permite conferir remetente, assunto, formatação e se a
mensagem cai no spam sem precisar criar um usuário para jogar fora depois.

Existe porque o diagnóstico "o e-mail não chegou" tem três culpados possíveis
(configuração, provedor e caixa de destino) e este script isola o primeiro:
se ele passa, a credencial está certa e o problema é do lado de lá.
"""

import sys

from src.config.config import get_settings
from src.utils.email import EmailSender, montar_email_senha_provisoria

SENHA_DE_MENTIRA = "TESTE-TESTE"


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: uv run python -m scripts.testar_email destino@exemplo.com")
        return 2

    destino = sys.argv[1]
    settings = get_settings()

    if not settings.GMAIL_OAUTH_REFRESH_TOKEN:
        print(
            "GMAIL_OAUTH_REFRESH_TOKEN está vazio no .env — o envio não é nem tentado.\n"
            "Rode scripts/gerar_refresh_token_gmail.py para gerar as três "
            "credenciais (GMAIL_OAUTH_CLIENT_ID, GMAIL_OAUTH_CLIENT_SECRET, "
            "GMAIL_OAUTH_REFRESH_TOKEN) e preencha o .env."
        )
        return 1

    print(f"usuário   : {settings.SMTP_USER}")
    print(f"remetente : {settings.SMTP_FROM or settings.SMTP_USER}")
    print(f"destino   : {destino}")

    assunto, texto, html = montar_email_senha_provisoria(
        "Fulano de Teste", SENHA_DE_MENTIRA, f"{settings.FRONTEND_URL.rstrip('/')}/login"
    )

    try:
        EmailSender().enviar(destino, f"[TESTE] {assunto}", texto, html)
    except Exception as erro:
        # A resposta crua da API é o que resolve o caso: token revogado,
        # client id/secret errados, ou escopo insuficiente pedem correções
        # diferentes.
        print(f"\nnão saiu: {type(erro).__name__}: {erro}")
        return 1

    print("\nenviado. Confira a caixa de entrada (e o spam).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
