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


def usuario(id=7, nome="Bia Martins", email="bia@al.insper.edu.br", ativo=True, desativadas=None):
    return SimpleNamespace(
        id=id, nome=nome, email_insper=email, ativo=ativo,
        notificacoes_email_desativadas=desativadas or [],
    )


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

    def _montar(*, pessoa=None, api_key="chave-fake", falha=False):
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
                RESEND_API_KEY=api_key, FRONTEND_URL="https://atlas.insperjr.com.br"
            ),
        )

        def executar(usuario_id=7, titulo="Banca de Alfa remarcada", corpo="De 06/08 para 20/08.",
                    rota="/projetos/3/cronograma", notificacao_id=99, tipo="banca_remarcada"):
            return enviar(
                notificacao_id=notificacao_id,
                usuario_id=usuario_id,
                tipo=tipo,
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

    def test_sem_resend_configurado_nao_tenta(self, montar):
        """Ambiente sem e-mail configurado: silêncio, não exceção. O aviso já
        está no sino, que é o canal principal."""
        executar, carimbos, sender = montar(api_key="")

        assert executar() is False
        assert sender.enviados == []
        assert carimbos == []

    def test_falha_de_smtp_nao_derruba_e_nao_carimba(self, montar):
        """A ação que gerou o evento já aconteceu. E a coluna não pode dizer
        que chegou quando não chegou."""
        executar, carimbos, sender = montar(falha=True)

        assert executar() is False
        assert carimbos == []

    def test_tipo_opcional_desativado_nao_manda(self, montar):
        """A pessoa desligou este tipo do e-mail — o sino continua registrando
        o evento normal, só o envio por fora é que não acontece."""
        executar, carimbos, sender = montar(pessoa=usuario(desativadas=["entrega_registrada"]))

        assert executar(tipo="entrega_registrada") is False
        assert sender.enviados == []
        assert carimbos == []

    def test_tipo_opcional_sem_desativar_manda_normal(self, montar):
        """Lista vazia (o padrão) = tudo ligado."""
        executar, carimbos, sender = montar()

        assert executar(tipo="entrega_registrada") is True
        assert len(sender.enviados) == 1

    def test_tipo_fixo_manda_mesmo_desativado(self, montar):
        """Só os tipos de TIPOS_NOTIFICACAO_OPCIONAIS respeitam a preferência —
        um tipo fixo sai sempre, mesmo com o nome dele (por engano ou não) na
        lista de desativados."""
        executar, carimbos, sender = montar(pessoa=usuario(desativadas=["banca_remarcada"]))

        assert executar(tipo="banca_remarcada") is True
        assert len(sender.enviados) == 1


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


class TestConexaoDuranteOEnvio:
    """A regra que faltava: o envio não pode segurar conexão de banco.

    O pool tem 5 conexões para a instância inteira e este módulo manda por 4
    threads. Enquanto cada uma segurava a sessão durante os até 15s da chamada
    ao Resend, sobrava uma conexão para todas as requisições — e quem estava
    no meio de um POST tomava `TimeoutError` do pool na primeira query depois
    do `commit()`. A tarefa entrava no banco e a request morria com 500 logo
    em seguida.

    O teste olha o único sintoma observável sem banco de verdade: nenhuma
    sessão pode estar aberta no instante em que o e-mail sai.
    """

    def test_nenhuma_sessao_aberta_quando_o_email_sai(self, montar):
        _, carimbos, _ = montar()
        abertas = []

        class SessaoRastreada(SessaoFake):
            def __init__(self):
                super().__init__()
                abertas.append(self)

        class SenderEspiao:
            def __init__(self):
                self.abertas_no_envio = None

            def enviar(self, destino, assunto, corpo_texto, corpo_html):
                self.abertas_no_envio = [s for s in abertas if not s.fechada]

        espiao = SenderEspiao()
        saiu = enviar(
            notificacao_id=99,
            usuario_id=7,
            tipo="banca_remarcada",
            titulo="Banca de Alfa remarcada",
            corpo=None,
            rota=None,
            sender=espiao,
            session_factory=SessaoRastreada,
        )

        assert saiu is True
        assert espiao.abertas_no_envio == []
        # Duas sessões curtas (ler o destinatário, carimbar), nunca uma só
        # atravessando o envio — e as duas fechadas no fim.
        assert len(abertas) == 2
        assert all(s.fechada for s in abertas)
        assert [id_ for id_, _ in carimbos] == [99]

    def test_envio_que_falha_nao_deixa_sessao_pendurada(self, montar):
        """Uma sessão vazando por request de erro esgota o pool igual — ou
        pior, porque erro de SMTP costuma vir em rajada."""
        _, carimbos, _ = montar()
        abertas = []

        class SessaoRastreada(SessaoFake):
            def __init__(self):
                super().__init__()
                abertas.append(self)

        class SenderQueFalha:
            def enviar(self, destino, assunto, corpo_texto, corpo_html):
                raise RuntimeError("SMTP fora do ar")

        saiu = enviar(
            notificacao_id=99,
            usuario_id=7,
            tipo="banca_remarcada",
            titulo="Banca de Alfa remarcada",
            corpo=None,
            rota=None,
            sender=SenderQueFalha(),
            session_factory=SessaoRastreada,
        )

        assert saiu is False
        assert all(s.fechada for s in abertas)
        # Sem envio não há o que carimbar: a coluna responde "chegou?".
        assert carimbos == []
