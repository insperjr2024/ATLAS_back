"""Confere se o SMTP do `.env` está mandando e-mail de verdade.

    uv run python -m scripts.testar_email seu.email@al.insper.edu.br

Manda o MESMO e-mail de boas-vindas do cadastro, com uma senha falsa e bem
marcada — é o que permite conferir remetente, assunto, formatação e se a
mensagem cai no spam sem precisar criar um usuário para jogar fora depois.

Existe porque o diagnóstico "o e-mail não chegou" tem três culpados possíveis
(configuração, provedor e caixa de destino) e este script isola o primeiro:
se ele passa, o SMTP está certo e o problema é do lado de lá.
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

    if not settings.SMTP_HOST:
        print(
            "SMTP_HOST está vazio no .env — o envio não é nem tentado.\n"
            "Preencha SMTP_HOST, SMTP_USER e SMTP_PASSWORD (no Gmail, uma App "
            "Password) e rode de novo."
        )
        return 1

    print(f"host      : {settings.SMTP_HOST}:{settings.SMTP_PORT}")
    print(f"usuário   : {settings.SMTP_USER}")
    print(f"remetente : {settings.SMTP_FROM or settings.SMTP_USER}")
    print(f"destino   : {destino}")

    assunto, texto, html = montar_email_senha_provisoria(
        "Fulano de Teste", SENHA_DE_MENTIRA, f"{settings.FRONTEND_URL.rstrip('/')}/login"
    )

    try:
        EmailSender().enviar(destino, f"[TESTE] {assunto}", texto, html)
    except Exception as erro:
        # A mensagem crua do smtplib é o que resolve o caso: "Username and
        # Password not accepted" (App Password errada) e "Connection refused"
        # (host/porta) pedem correções diferentes.
        print(f"\n❌ não saiu: {type(erro).__name__}: {erro}")
        return 1

    print("\n✅ enviado. Confira a caixa de entrada (e o spam).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
