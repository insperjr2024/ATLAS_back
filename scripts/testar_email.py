"""Confere se o Resend do `.env` está mandando e-mail de verdade.

    uv run python -m scripts.testar_email seu.email@al.insper.edu.br

Manda o MESMO e-mail de boas-vindas do cadastro, com uma senha falsa e bem
marcada — é o que permite conferir remetente, assunto, formatação e se a
mensagem cai no spam sem precisar criar um usuário para jogar fora depois.

Existe porque o diagnóstico "o e-mail não chegou" tem três culpados possíveis
(configuração, provedor e caixa de destino) e este script isola o primeiro:
se ele passa, a credencial está certa e o problema é do lado de lá.
"""

import sys
from datetime import datetime

from src.config.config import get_settings
from src.utils.email import EmailSender, montar_email_senha_provisoria

SENHA_DE_MENTIRA = "TESTE-TESTE"


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: uv run python -m scripts.testar_email destino@exemplo.com")
        return 2

    destino = sys.argv[1]
    settings = get_settings()

    if not settings.RESEND_API_KEY:
        print(
            "RESEND_API_KEY está vazia no .env — o envio não é nem tentado.\n"
            "Gera uma em resend.com/api-keys e preenche o .env."
        )
        return 1

    print(f"usuário   : {settings.SMTP_USER}")
    print(f"remetente : {settings.SMTP_FROM or settings.SMTP_USER}")
    print(f"destino   : {destino}")

    # O código de data/hora identifica ESTA execução.
    #
    # Sem ele o script mandava texto idêntico toda vez — mesmo nome falso,
    # mesma senha falsa, mesmo assunto —, e quem depura entrega manda o teste
    # várias vezes seguidas. Com todas as tentativas iguais na caixa, não dá
    # para dizer qual chegou, se alguma chegou duas vezes, ou se a que você
    # está olhando é a de agora ou a de dez minutos atrás.
    #
    # ⚠ Não é proteção contra deduplicação do destinatário. Isso foi testado
    # em 17/08/2026 — duas mensagens de conteúdo byte a byte idêntico,
    # mandadas com 12s de diferença para a mesma caixa do Gmail, chegaram as
    # duas. O código serve para você conseguir LER o resultado do teste, não
    # para fazer a mensagem passar.
    codigo = datetime.now().strftime("%d/%m %H:%M:%S")
    assunto, texto, html = montar_email_senha_provisoria(
        "Fulano de Teste", SENHA_DE_MENTIRA, f"{settings.FRONTEND_URL.rstrip('/')}/login"
    )
    texto = f"{texto}\nTeste enviado em {codigo}.\n"
    html = f'{html}<p style="color:#666;font-size:12px">Teste enviado em {codigo}.</p>'
    print(f"código    : {codigo}")

    try:
        EmailSender().enviar(destino, f"[TESTE {codigo}] {assunto}", texto, html)
    except Exception as erro:
        # A resposta crua da API é o que resolve o caso: API key errada,
        # domínio ainda não verificado, ou remetente fora do domínio
        # verificado pedem correções diferentes.
        print(f"\nnão saiu: {type(erro).__name__}: {erro}")
        return 1

    print("\nenviado. Confira a caixa de entrada (e o spam).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
