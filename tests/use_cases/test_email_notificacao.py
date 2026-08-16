"""O espelho do sino no e-mail: quem recebe, o que chega e o que não derruba.

Três regras dominam estes testes, e as três já existiam no sino — o e-mail
apenas não pode desobedecê-las:

- **Quem não é mais do núcleo não recebe.** Ex-membro e desligado (§10)
  continuam com as notificações antigas no banco; o e-mail é o canal que sai
  da plataforma, e mandar para o endereço de quem saiu é vazamento.
- **SMTP fora do ar não derruba nada.** Mesma doutrina de
  `registrar_notificacao`: o aviso é efeito colateral do trabalho.
- **`email_enviado_em` responde "chegou?", não "tentamos?".** Só é carimbado
  depois do envio dar certo.

`enviar_email_notificacao` instancia os repositórios dentro da função, então o
teste troca as CLASSES no módulo (via `monkeypatch`) — mesmo idioma de
`test_destinatarios_notificacao.py`. O `EmailSenderFake` é escrito à mão, como
em `test_senha_provisoria.py`: o repo não usa `unittest.mock`.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.notificacao import enviar_email_notificacao
from src.use_cases.notificacao.enviar_email_notificacao import _link, enviar
from src.utils.email import montar_email_notificacao


def usuario(id=7, nome="Bia Martins", email="bia@al.insper.edu.br", ativo=True):
    return SimpleNamespace(id=id, nome=nome, email_insper=email, ativo=ativo)


class EmailSenderFake:
    def __init__(self, falha=False):
        self.enviados = []
        self.falha = falha

    def enviar(self, destino, assunto, corpo_texto, corpo_html):
        if self.falha:
            raise RuntimeError("SMTP fora do ar")
        self.enviados.append(
            {"destino": destino, "assunto": assunto, "texto": corpo_texto, "html": corpo_html}
        )


class SessaoFake:
    """Só precisa existir e saber fechar: quem consulta são os repositórios,
    e eles estão trocados por dublês."""

    def __init__(self):
        self.fechada = False

    def close(self):
        self.fechada = True


@pytest.fixture
def montar(monkeypatch):
    """Devolve `(enviar_com_fakes, carimbos, sender)`.

    `carimbos` acumula os `update` que o envio fez na notificação — é como o
    teste enxerga o `email_enviado_em` sem banco nenhum.
    """

    def _montar(*, pessoa=None, refresh_token="token-fake", falha=False):
        pessoa = pessoa if pessoa is not None else usuario()
        carimbos = []
        sender = EmailSenderFake(falha=falha)

        class UsuarioRepositoryFake:
            def __init__(self, db): pass
            def get_by_id(self, usuario_id):
                return pessoa if pessoa and pessoa.id == usuario_id else None

        class NotificacaoRepositoryFake:
            def __init__(self, db): pass
            def update(self, registro_id, **campos):
                carimbos.append((registro_id, campos))

        monkeypatch.setattr(enviar_email_notificacao, "UsuarioRepository", UsuarioRepositoryFake)
        monkeypatch.setattr(
            enviar_email_notificacao, "NotificacaoRepository", NotificacaoRepositoryFake
        )
        monkeypatch.setattr(
            enviar_email_notificacao,
            "get_settings",
            lambda: SimpleNamespace(
                GMAIL_OAUTH_REFRESH_TOKEN=refresh_token, FRONTEND_URL="https://atlas.insperjr.com.br"
            ),
        )

        def executar(usuario_id=7, titulo="Banca de Alfa remarcada", corpo="De 06/08 para 20/08.",
                    rota="/projetos/3/cronograma", notificacao_id=99):
            return enviar(
                notificacao_id=notificacao_id,
                usuario_id=usuario_id,
                titulo=titulo,
                corpo=corpo,
                rota=rota,
                sender=sender,
                session_factory=SessaoFake,
            )

        return executar, carimbos, sender

    return _montar


class TestEnvio:
    def test_email_vai_para_o_endereco_cadastrado_e_carimba(self, montar):
        """O caminho feliz: sai para o `email_insper` e a coluna registra."""
        executar, carimbos, sender = montar()

        assert executar() is True

        assert len(sender.enviados) == 1
        assert sender.enviados[0]["destino"] == "bia@al.insper.edu.br"
        assert [id_ for id_, _ in carimbos] == [99]
        assert "email_enviado_em" in carimbos[0][1]

    def test_titulo_e_corpo_do_sino_chegam_no_email(self, montar):
        """A redação é a MESMA do sino — quem lê os dois canais lê a mesma
        notícia, não duas versões dela."""
        executar, _, sender = montar()
        executar()

        enviado = sender.enviados[0]
        assert "Banca de Alfa remarcada" in enviado["assunto"]
        assert "Banca de Alfa remarcada" in enviado["texto"]
        assert "De 06/08 para 20/08." in enviado["texto"]
        # A rota do sino vira URL absoluta: no e-mail não existe "página atual".
        assert "https://atlas.insperjr.com.br/projetos/3/cronograma" in enviado["texto"]

    def test_ex_membro_nao_recebe(self, montar):
        """§10: quem saiu não é mais avisado fora da plataforma."""
        executar, carimbos, sender = montar(pessoa=usuario(ativo=False))

        assert executar() is False
        assert sender.enviados == []
        assert carimbos == []

    def test_usuario_inexistente_nao_estoura(self, montar):
        executar, _, sender = montar()

        assert executar(usuario_id=404) is False
        assert sender.enviados == []

    def test_sem_gmail_oauth_configurado_nao_tenta(self, montar):
        """Ambiente sem e-mail configurado: silêncio, não exceção. O aviso já
        está no sino, que é o canal principal."""
        executar, carimbos, sender = montar(refresh_token="")

        assert executar() is False
        assert sender.enviados == []
        assert carimbos == []

    def test_falha_de_smtp_nao_derruba_e_nao_carimba(self, montar):
        """A ação que gerou o evento já aconteceu. E a coluna não pode dizer
        que chegou quando não chegou."""
        executar, carimbos, sender = montar(falha=True)

        assert executar() is False
        assert carimbos == []


class TestLink:
    def test_rota_do_sino_vira_url_absoluta(self, montar):
        montar()  # instala o `get_settings` fake
        assert _link("/bancas/12") == "https://atlas.insperjr.com.br/bancas/12"

    def test_sem_rota_cai_na_central(self, montar):
        """Todo evento aparece em /notificacoes, então o link nunca quebra."""
        montar()
        assert _link(None) == "https://atlas.insperjr.com.br/notificacoes"

    def test_nao_duplica_a_barra(self, montar):
        montar()
        assert _link("projetos/3") == "https://atlas.insperjr.com.br/projetos/3"


class TestRedacao:
    """`montar_email_notificacao` é pura — dá para exercitar sem nada em volta."""

    def test_assunto_repete_o_titulo_com_prefixo(self):
        assunto, _, _ = montar_email_notificacao("Bia", "Você entrou no projeto Alfa", None, "#")
        assert assunto == "[ATLAS] Você entrou no projeto Alfa"

    def test_evento_sem_corpo_nao_deixa_paragrafo_vazio(self):
        """Boa parte dos eventos só tem título — um branco no meio do e-mail
        parece conteúdo que se perdeu no caminho."""
        _, texto, html = montar_email_notificacao("Bia", "Alfa — Diagnóstico entregue", None, "#")
        assert "<p></p>" not in html
        assert "\n\n\n" not in texto

    def test_corpo_entra_quando_existe(self):
        _, texto, html = montar_email_notificacao("Bia", "Banca remarcada", "De 06/08 para 20/08.", "#")
        assert "De 06/08 para 20/08." in texto
        assert "De 06/08 para 20/08." in html
