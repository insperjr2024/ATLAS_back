"""`EmailSender.enviar` (§ e-mail, 2026-09-23).

⚠ Só o redirecionamento de teste (`EMAIL_TESTE_DESTINO`) — o resto do envio
(carimbo, corpo, erro do Resend) é coberto do lado de cima em
`test_email_notificacao.py`, que já usa um `EmailSenderFake` próprio.
"""

from types import SimpleNamespace

import src.utils.email as email_mod
from src.utils.email import EmailSender


def _montar(monkeypatch, *, email_teste_destino=""):
    chamadas = []

    class RespostaFake:
        is_error = False
        status_code = 200
        text = ""

    def post_fake(url, *, headers, json, timeout):
        chamadas.append(json)
        return RespostaFake()

    monkeypatch.setattr(email_mod.httpx, "post", post_fake)
    monkeypatch.setattr(
        email_mod,
        "get_settings",
        lambda: SimpleNamespace(
            RESEND_API_KEY="chave-fake",
            SMTP_FROM="Insper Jr <naoresponda@insperjr.org>",
            SMTP_USER="",
            EMAIL_TESTE_DESTINO=email_teste_destino,
        ),
    )
    return chamadas


class TestRedirecionamentoDeTeste:
    def test_sem_destino_de_teste_manda_pro_endereco_real(self, monkeypatch):
        chamadas = _montar(monkeypatch, email_teste_destino="")

        EmailSender().enviar("real@exemplo.com", "Assunto", "texto", "<p>html</p>")

        assert chamadas[0]["to"] == ["real@exemplo.com"]
        assert chamadas[0]["subject"] == "Assunto"

    def test_com_destino_de_teste_redireciona_e_marca_o_assunto(self, monkeypatch):
        chamadas = _montar(monkeypatch, email_teste_destino="teste@exemplo.com")

        EmailSender().enviar("real@exemplo.com", "Assunto", "texto", "<p>html</p>")

        assert chamadas[0]["to"] == ["teste@exemplo.com"]
        assert chamadas[0]["subject"] == "[teste — seria para real@exemplo.com] Assunto"

    def test_destinatario_ja_e_o_de_teste_nao_marca_o_assunto(self, monkeypatch):
        chamadas = _montar(monkeypatch, email_teste_destino="teste@exemplo.com")

        EmailSender().enviar("teste@exemplo.com", "Assunto", "texto", "<p>html</p>")

        assert chamadas[0]["to"] == ["teste@exemplo.com"]
        assert chamadas[0]["subject"] == "Assunto"
