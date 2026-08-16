"""Gera o refresh token OAuth do Gmail, uma vez só, para colar no `.env` e
no Render (GMAIL_OAUTH_CLIENT_ID, GMAIL_OAUTH_CLIENT_SECRET,
GMAIL_OAUTH_REFRESH_TOKEN).

    uv run python -m scripts.gerar_refresh_token_gmail <client_id> <client_secret>

Pede o client_id e o client_secret de uma credencial OAuth tipo "Desktop
app", criada no Google Cloud Console (APIs e serviços -> Credenciais ->
Criar credenciais -> ID do cliente OAuth -> Aplicativo para computador).
Abre o navegador, você loga com a conta que vai mandar os e-mails e
autoriza; o script captura o código de volta na porta 8765 (o Google
libera qualquer porta de loopback para esse tipo de credencial, sem
precisar cadastrar a porta em lugar nenhum), troca o código por um refresh
token e imprime as três linhas prontas para colar.

`prompt=consent` força o Google a emitir um refresh token mesmo se essa
conta já tiver autorizado esse client id antes — sem isso, rodar de novo
devolveria só um access token, sem refresh token.
"""

import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

PORTA = 8765
REDIRECT_URI = f"http://localhost:{PORTA}"
ESCOPO = "https://www.googleapis.com/auth/gmail.send"


class _Handler(BaseHTTPRequestHandler):
    codigo: str | None = None

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        _Handler.codigo = query.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<p>Autorizado. Pode fechar esta aba e voltar ao terminal.</p>".encode())

    def log_message(self, *args):
        pass  # silencioso: só interessa o resultado no terminal


def main() -> int:
    if len(sys.argv) < 3:
        print("uso: uv run python -m scripts.gerar_refresh_token_gmail <client_id> <client_secret>")
        return 2

    client_id, client_secret = sys.argv[1], sys.argv[2]

    url_auth = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": ESCOPO,
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    print(f"Abrindo o navegador para autorizar. Se não abrir sozinho, acesse:\n{url_auth}\n")
    webbrowser.open(url_auth)

    servidor = HTTPServer(("localhost", PORTA), _Handler)
    servidor.handle_request()  # bloqueia até o navegador chamar de volta

    if not _Handler.codigo:
        print("Não recebi o código de autorização. Tente de novo.")
        return 1

    resposta = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": _Handler.codigo,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    resposta.raise_for_status()
    tokens = resposta.json()

    if "refresh_token" not in tokens:
        print(
            "O Google não devolveu refresh token. Provavelmente essa conta já "
            "tinha autorizado esse client id antes, mesmo com prompt=consent — "
            "revogue o acesso em myaccount.google.com/permissions e rode de novo."
        )
        return 1

    print("\nCole estas três linhas no .env e no Render:\n")
    print(f"GMAIL_OAUTH_CLIENT_ID={client_id}")
    print(f"GMAIL_OAUTH_CLIENT_SECRET={client_secret}")
    print(f"GMAIL_OAUTH_REFRESH_TOKEN={tokens['refresh_token']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
