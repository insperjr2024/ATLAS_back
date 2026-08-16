from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    #: 7 dias. O token é renovado a cada vez que a plataforma abre (ver
    #: `POST /auth/renovar`), então quem usa toda semana nunca reloga; o prazo
    #: só corre para sessão abandonada.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    UPLOADS_DIR: str = "uploads"

    # ─── Recuperação de senha ────────────────────────────────────────────
    # Tudo com default para o `.env` de quem já clonou continuar valendo —
    # mesmo motivo do UPLOADS_DIR acima. Sem GMAIL_OAUTH_REFRESH_TOKEN
    # preenchido o envio falha explicitamente em vez de fingir que mandou.
    #
    # SMTP_HOST/PORT/PASSWORD saíram: o envio é pela API do Gmail (OAuth),
    # não por SMTP direto — o Render bloqueia as portas de SMTP no plano
    # free (ver `src/utils/email.py`). SMTP_USER e SMTP_FROM continuam,
    # viram só o cabeçalho "From" da mensagem.
    SMTP_USER: str = ""
    #: Remetente exibido. Vazio = usa o SMTP_USER.
    SMTP_FROM: str = ""
    #: As três credenciais da conta OAuth "Desktop app" criada no Google
    #: Cloud Console. O refresh token é gerado uma vez, localmente, com
    #: `scripts/gerar_refresh_token_gmail.py`.
    GMAIL_OAUTH_CLIENT_ID: str = ""
    GMAIL_OAUTH_CLIENT_SECRET: str = ""
    GMAIL_OAUTH_REFRESH_TOKEN: str = ""
    #: Base do link que vai no e-mail. Em produção precisa ser o domínio real,
    #: senão o link aponta para a máquina de quem enviou.
    FRONTEND_URL: str = "http://localhost:5173"
    #: Janela de validade do link. Curta de propósito: é o tempo em que um
    #: e-mail vazado ainda serve para trocar a senha de alguém.
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    #: Intervalo mínimo entre dois pedidos do mesmo usuário, em segundos.
    #: Sem isso o endpoint vira um canhão de spam para a caixa de qualquer um.
    RESET_INTERVALO_MINIMO_SEGUNDOS: int = 120

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()