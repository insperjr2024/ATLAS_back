"""O fluxo de "esqueci minha senha" — os dois passos e o que os protege.

Duas regras dominam estes testes e vale dizer por quê:

- **Solicitar responde sempre igual.** Existir ou não o e-mail, estar ativo ou
  não, ter pedido há 10 segundos ou não: a resposta é a mesma frase. O que
  muda é se o e-mail sai. Testar isso é testar que a rota não vira um
  verificador de quem é membro do núcleo.
- **O token é de uso único.** É o que separa esta implementação de um JWT
  assinado, que continuaria valendo depois de usado.
"""

from datetime import datetime, timedelta

import pytest

from src.use_cases.auth.redefinir_senha import (
    RedefinirSenhaRequest,
    RedefinirSenhaUseCase,
)
from src.use_cases.auth.solicitar_recuperacao import (
    RESPOSTA_NEUTRA,
    SolicitarRecuperacaoRequest,
    SolicitarRecuperacaoUseCase,
    hash_token,
)
from src.utils.exceptions import RegraDeNegocioError

AGORA = datetime(2026, 8, 5, 10, 0, 0)


class UsuarioFake:
    def __init__(self, id=1, nome="Ana Souza", email="ana@al.insper.edu.br", ativo=True):
        self.id = id
        self.nome = nome
        self.email_insper = email
        self.ativo = ativo
        self.senha_hash = "hash_antigo"


class TokenFake:
    def __init__(self, usuario_id, token_hash, expira_em, usado_em=None, criado_em=AGORA):
        self.id = 1
        self.usuario_id = usuario_id
        self.token_hash = token_hash
        self.expira_em = expira_em
        self.usado_em = usado_em
        self.criado_em = criado_em


class UsuarioRepositoryFake:
    def __init__(self, *usuarios):
        self._usuarios = list(usuarios)

    def get_by_email_insper(self, email):
        return next((u for u in self._usuarios if u.email_insper == email), None)

    def get_by_id(self, usuario_id):
        return next((u for u in self._usuarios if u.id == usuario_id), None)

    def update(self, usuario_id, **campos):
        usuario = self.get_by_id(usuario_id)
        for chave, valor in campos.items():
            setattr(usuario, chave, valor)
        return usuario


class TokenRepositoryFake:
    def __init__(self, *tokens):
        self._tokens = list(tokens)
        self.criados = []
        self.invalidados = 0

    def get_por_hash(self, token_hash):
        return next((t for t in self._tokens if t.token_hash == token_hash), None)

    def get_ultimo_do_usuario(self, usuario_id):
        do_usuario = [t for t in self._tokens if t.usuario_id == usuario_id]
        return max(do_usuario, key=lambda t: t.criado_em) if do_usuario else None

    def invalidar_pendentes(self, usuario_id, quando):
        pendentes = [
            t for t in self._tokens if t.usuario_id == usuario_id and t.usado_em is None
        ]
        for t in pendentes:
            t.usado_em = quando
        self.invalidados += len(pendentes)
        return len(pendentes)

    def create(self, **kwargs):
        token = TokenFake(**kwargs, criado_em=AGORA)
        self._tokens.append(token)
        self.criados.append(kwargs)
        return token

    def marcar_usado(self, token, quando):
        token.usado_em = quando


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


def montar_solicitacao(*usuarios, tokens=()):
    uc = SolicitarRecuperacaoUseCase.__new__(SolicitarRecuperacaoUseCase)
    uc.db = None
    uc.usuario_repository = UsuarioRepositoryFake(*usuarios)
    uc.token_repository = TokenRepositoryFake(*tokens)
    uc.email_sender = EmailSenderFake()
    return uc


def montar_redefinicao(*usuarios, tokens=()):
    uc = RedefinirSenhaUseCase.__new__(RedefinirSenhaUseCase)
    uc.db = None
    uc.usuario_repository = UsuarioRepositoryFake(*usuarios)
    uc.token_repository = TokenRepositoryFake(*tokens)
    return uc


class TestSolicitarRecuperacao:
    def test_email_conhecido_gera_token_e_envia(self):
        uc = montar_solicitacao(UsuarioFake())
        resposta = uc.execute(
            SolicitarRecuperacaoRequest(email_insper="ana@al.insper.edu.br"), agora=AGORA
        )
        assert resposta == RESPOSTA_NEUTRA
        assert len(uc.token_repository.criados) == 1
        assert len(uc.email_sender.enviados) == 1
        assert uc.email_sender.enviados[0]["destino"] == "ana@al.insper.edu.br"

    def test_email_desconhecido_responde_igual_e_nao_envia(self):
        """O ponto da regra: a resposta não distingue quem existe de quem não."""
        uc = montar_solicitacao(UsuarioFake())
        resposta = uc.execute(
            SolicitarRecuperacaoRequest(email_insper="ninguem@gmail.com"), agora=AGORA
        )
        assert resposta == RESPOSTA_NEUTRA
        assert uc.email_sender.enviados == []
        assert uc.token_repository.criados == []

    def test_usuario_inativo_nao_recebe_link(self):
        """§10: quem foi desligado não volta pelo reset."""
        uc = montar_solicitacao(UsuarioFake(ativo=False))
        resposta = uc.execute(
            SolicitarRecuperacaoRequest(email_insper="ana@al.insper.edu.br"), agora=AGORA
        )
        assert resposta == RESPOSTA_NEUTRA
        assert uc.email_sender.enviados == []

    def test_o_banco_nunca_recebe_o_token_cru(self):
        uc = montar_solicitacao(UsuarioFake())
        uc.execute(SolicitarRecuperacaoRequest(email_insper="ana@al.insper.edu.br"), agora=AGORA)
        gravado = uc.token_repository.criados[0]["token_hash"]
        link = uc.email_sender.enviados[0]["texto"]
        assert len(gravado) == 64                 # sha256 em hex
        assert gravado not in link                # o que vai no e-mail é o cru
        assert hash_token(link.split("token=")[1].split()[0]) == gravado

    def test_pedido_novo_invalida_o_anterior(self):
        """Dois links válidos ao mesmo tempo = o mais antigo, com mais tempo
        exposto na caixa de e-mail, continuaria servindo."""
        antigo = TokenFake(1, "hash_antigo", AGORA + timedelta(minutes=30))
        uc = montar_solicitacao(UsuarioFake(), tokens=(antigo,))
        # `criado_em` bem no passado para não esbarrar no freio de spam.
        antigo.criado_em = AGORA - timedelta(hours=1)
        uc.execute(SolicitarRecuperacaoRequest(email_insper="ana@al.insper.edu.br"), agora=AGORA)
        assert antigo.usado_em == AGORA
        assert uc.token_repository.invalidados == 1

    def test_envio_que_falha_nao_deixa_rastro(self):
        """Prende a ORDEM: enviar primeiro, gravar depois.

        Na ordem inversa, um SMTP fora do ar deixaria um token órfão no banco
        — que ainda liga o freio de spam e impede a pessoa de tentar de novo.
        Ela tomaria erro E ficaria bloqueada. Aqui, falha não grava nada.
        """
        antigo = TokenFake(
            1, "hash_antigo", AGORA + timedelta(minutes=30),
            criado_em=AGORA - timedelta(hours=1),
        )
        uc = montar_solicitacao(UsuarioFake(), tokens=(antigo,))
        uc.email_sender = EmailSenderFake(falha=True)

        with pytest.raises(RuntimeError):
            uc.execute(
                SolicitarRecuperacaoRequest(email_insper="ana@al.insper.edu.br"), agora=AGORA
            )

        assert uc.token_repository.criados == []      # nada gravado
        assert uc.token_repository.invalidados == 0   # nada derrubado
        assert antigo.usado_em is None                # o link anterior sobrevive

    def test_pedido_seguido_e_barrado_sem_revelar(self):
        recente = TokenFake(
            1, "hash_recente", AGORA + timedelta(minutes=30),
            criado_em=AGORA - timedelta(seconds=10),
        )
        uc = montar_solicitacao(UsuarioFake(), tokens=(recente,))
        resposta = uc.execute(
            SolicitarRecuperacaoRequest(email_insper="ana@al.insper.edu.br"), agora=AGORA
        )
        assert resposta == RESPOSTA_NEUTRA       # mesma frase de sempre
        assert uc.email_sender.enviados == []    # mas não manda nada


class TestRedefinirSenha:
    def _token_valido(self, cru="token-cru-de-teste"):
        return cru, TokenFake(1, hash_token(cru), AGORA + timedelta(minutes=10))

    def test_token_valido_troca_a_senha(self):
        cru, token = self._token_valido()
        usuario = UsuarioFake()
        uc = montar_redefinicao(usuario, tokens=(token,))
        uc.execute(RedefinirSenhaRequest(token=cru, nova_senha="senhanova123"), agora=AGORA)
        assert usuario.senha_hash != "hash_antigo"
        assert token.usado_em == AGORA

    def test_o_mesmo_token_nao_serve_duas_vezes(self):
        """O motivo de existir a tabela em vez de um JWT."""
        cru, token = self._token_valido()
        uc = montar_redefinicao(UsuarioFake(), tokens=(token,))
        uc.execute(RedefinirSenhaRequest(token=cru, nova_senha="senhanova123"), agora=AGORA)
        with pytest.raises(RegraDeNegocioError, match="inválido ou já expirou"):
            uc.execute(RedefinirSenhaRequest(token=cru, nova_senha="outrasenha123"), agora=AGORA)

    def test_token_expirado_e_recusado(self):
        cru = "token-cru-de-teste"
        token = TokenFake(1, hash_token(cru), AGORA - timedelta(minutes=1))
        uc = montar_redefinicao(UsuarioFake(), tokens=(token,))
        with pytest.raises(RegraDeNegocioError, match="inválido ou já expirou"):
            uc.execute(RedefinirSenhaRequest(token=cru, nova_senha="senhanova123"), agora=AGORA)

    def test_token_inexistente_e_recusado(self):
        uc = montar_redefinicao(UsuarioFake())
        with pytest.raises(RegraDeNegocioError, match="inválido ou já expirou"):
            uc.execute(
                RedefinirSenhaRequest(token="nunca-existiu", nova_senha="senhanova123"),
                agora=AGORA,
            )

    def test_usuario_inativo_nao_redefine(self):
        cru, token = self._token_valido()
        uc = montar_redefinicao(UsuarioFake(ativo=False), tokens=(token,))
        with pytest.raises(RegraDeNegocioError, match="inválido ou já expirou"):
            uc.execute(RedefinirSenhaRequest(token=cru, nova_senha="senhanova123"), agora=AGORA)

    @pytest.mark.parametrize("senha", ["", "123", "1234567"])
    def test_senha_curta_e_recusada(self, senha):
        cru, token = self._token_valido()
        uc = montar_redefinicao(UsuarioFake(), tokens=(token,))
        with pytest.raises(RegraDeNegocioError, match="pelo menos"):
            uc.execute(RedefinirSenhaRequest(token=cru, nova_senha=senha), agora=AGORA)

    def test_senha_curta_nao_queima_o_token(self):
        """A validação vem antes de tocar no token — errar o tamanho da senha
        não pode custar o link inteiro."""
        cru, token = self._token_valido()
        uc = montar_redefinicao(UsuarioFake(), tokens=(token,))
        with pytest.raises(RegraDeNegocioError):
            uc.execute(RedefinirSenhaRequest(token=cru, nova_senha="123"), agora=AGORA)
        assert token.usado_em is None
        uc.execute(RedefinirSenhaRequest(token=cru, nova_senha="senhanova123"), agora=AGORA)
