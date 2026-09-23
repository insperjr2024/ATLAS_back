from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    #: 60 min (2026-09-04, a pedido — era 7 dias). A renovação (`POST
    #: /auth/renovar`) só roda quando o app CARREGA, não num intervalo fixo
    #: enquanto a aba fica aberta — então, diferente do prazo de 7 dias, uma
    #: sessão ativa numa aba aberta sem reload pode expirar NO MEIO do uso, e
    #: a próxima chamada à API vira 401. Foi um troca consciente: segurança
    #: de sessão curta em vez de nunca incomodar quem está ativo.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ─── Recuperação de senha ────────────────────────────────────────────
    # Tudo com default para o `.env` de quem já clonou continuar valendo. Sem
    # RESEND_API_KEY preenchida o envio falha explicitamente em vez de fingir
    # que mandou.
    #
    # SMTP_HOST/PORT/PASSWORD não existem: o envio é pela API do Resend
    # (HTTPS), não por SMTP direto — ver `src/utils/email.py`. SMTP_USER e
    # SMTP_FROM continuam, viram só o cabeçalho "From" da mensagem.
    SMTP_USER: str = ""
    #: Remetente exibido. Vazio = usa o SMTP_USER.
    SMTP_FROM: str = ""
    #: A API key gerada no dashboard do Resend (resend.com/api-keys).
    RESEND_API_KEY: str = ""
    #: ⭐ 2026-09-23 — a pedido: enquanto Contratos está em teste em cima do
    #: banco de PRODUÇÃO de verdade, todo e-mail (não só o de Contratos —
    #: qualquer notificação) sai redirecionado pra este endereço em vez do
    #: destinatário real. Vazio (o padrão) = comportamento normal. Some do
    #: .env assim que o teste acabar.
    EMAIL_TESTE_DESTINO: str = ""
    #: Base do link que vai no e-mail. Em produção precisa ser o domínio real,
    #: senão o link aponta para a máquina de quem enviou.
    FRONTEND_URL: str = "http://localhost:5173"
    #: Janela de validade do link. Curta de propósito: é o tempo em que um
    #: e-mail vazado ainda serve para trocar a senha de alguém.
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    #: Intervalo mínimo entre dois pedidos do mesmo usuário, em segundos.
    #: Sem isso o endpoint vira um canhão de spam para a caixa de qualquer um.
    RESET_INTERVALO_MINIMO_SEGUNDOS: int = 120

    # ─── Documentos jurídicos (§ Contratos) ──────────────────────────────
    #: Caminho do executável do LibreOffice, usado para converter o .docx
    #: gerado em .pdf (`utils/pdf.py`). "soffice" cru assume que está no PATH
    #: do servidor — nem sempre verdade (comum faltar em container/Windows).
    SOFFICE_PATH: str = "soffice"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()