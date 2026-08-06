"""O primeiro acesso: senha provisória no cadastro e a troca obrigatória.

Duas regras dominam estes testes:

- **A senha em claro só existe na resposta de quem cadastrou.** O que fica no
  banco é o hash, e o e-mail é o canal preferencial — não o único.
- **E-mail que não sai não desfaz o cadastro.** É o oposto da doutrina de
  `solicitar_recuperacao.py` ("envio antes da escrita"), e de propósito: aqui
  existe uma pessoa na tela com a senha na mão para contornar a falha.

Fakes escritos à mão, como no resto da suíte (`test_recuperacao_senha.py`) —
o repo não usa `unittest.mock`.
"""

import pytest

from src.use_cases.auth.definir_senha import DefinirSenhaRequest, DefinirSenhaUseCase
from src.use_cases.auth.registrar import RegistrarRequest, RegistrarUseCase
from src.use_cases.auth.senha_provisoria import ReenviarSenhaProvisoriaUseCase
from src.utils.exceptions import RegraDeNegocioError
from src.utils.senha import (
    ALFABETO_PROVISORIA,
    TAMANHO_MINIMO_SENHA,
    gerar_senha_provisoria,
    hash_senha,
    verificar_senha,
)


class UsuarioFake:
    def __init__(self, id=1, nome="Bia Martins", email="bia@al.insper.edu.br", ativo=True):
        self.id = id
        self.nome = nome
        self.email_insper = email
        self.ativo = ativo
        self.cargo_id = 3
        self.posicao = "consultor"
        self.status = "ativo" if ativo else "desligado"
        self.senha_hash = hash_senha("senha-antiga-dela")
        self.senha_provisoria = False


class UsuarioRepositoryFake:
    def __init__(self, *usuarios):
        self._usuarios = list(usuarios)
        self.proximo_id = len(self._usuarios) + 1

    def get_by_email_insper(self, email):
        return next((u for u in self._usuarios if u.email_insper == email), None)

    def get_by_id(self, usuario_id):
        return next((u for u in self._usuarios if u.id == usuario_id), None)

    def create(self, **campos):
        usuario = UsuarioFake(id=self.proximo_id)
        self.proximo_id += 1
        for chave, valor in campos.items():
            setattr(usuario, chave, valor)
        self._usuarios.append(usuario)
        return usuario

    def update(self, usuario_id, **campos):
        usuario = self.get_by_id(usuario_id)
        for chave, valor in campos.items():
            setattr(usuario, chave, valor)
        return usuario


class CargoFake:
    def __init__(self, id=3):
        self.id = id


class CargoRepositoryFake:
    def get_by_id(self, cargo_id):
        return CargoFake(cargo_id)


class ConfiguracaoRepositoryFake:
    def get(self):
        return type("Configuracao", (), {"cargo_padrao_id": 3})()


class MembroRepositoryFake:
    def contar_ativos_por_usuario(self):
        return {}


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


def montar_registro(*usuarios, falha_email=False):
    uc = RegistrarUseCase.__new__(RegistrarUseCase)
    uc.usuario_repository = UsuarioRepositoryFake(*usuarios)
    uc.configuracao_repository = ConfiguracaoRepositoryFake()
    uc.cargo_repository = CargoRepositoryFake()
    uc.email_sender = EmailSenderFake(falha=falha_email)
    return uc


def montar_reenvio(*usuarios, falha_email=False):
    uc = ReenviarSenhaProvisoriaUseCase.__new__(ReenviarSenhaProvisoriaUseCase)
    uc.usuario_repository = UsuarioRepositoryFake(*usuarios)
    uc.email_sender = EmailSenderFake(falha=falha_email)
    return uc


def montar_definicao(*usuarios):
    uc = DefinirSenhaUseCase.__new__(DefinirSenhaUseCase)
    uc.usuario_repository = UsuarioRepositoryFake(*usuarios)
    return uc


PEDIDO = RegistrarRequest(nome="Caio Ferreira", email_insper="caio@al.insper.edu.br")


class TestGerarSenhaProvisoria:
    def test_formato_em_dois_blocos(self):
        senha = gerar_senha_provisoria()
        bloco_a, bloco_b = senha.split("-")
        assert len(bloco_a) == len(bloco_b) == 5

    def test_so_usa_o_alfabeto_sem_ambiguidade(self):
        """Sem `0/O` e `1/l/I`: esta senha é lida de um e-mail e digitada à mão."""
        for _ in range(50):
            assert set(gerar_senha_provisoria().replace("-", "")) <= set(ALFABETO_PROVISORIA)

    def test_passa_do_tamanho_minimo_exigido(self):
        """Senão a própria provisória seria recusada pela régua de senha."""
        assert len(gerar_senha_provisoria()) >= TAMANHO_MINIMO_SENHA

    def test_duas_chamadas_nao_repetem(self):
        assert len({gerar_senha_provisoria() for _ in range(20)}) == 20


class TestCadastro:
    def test_cria_com_senha_provisoria_e_manda_o_email(self):
        uc = montar_registro()

        resposta = uc.execute(PEDIDO)

        criado = uc.usuario_repository.get_by_email_insper("caio@al.insper.edu.br")
        assert criado.senha_provisoria is True
        assert resposta["email_enviado"] is True
        assert uc.email_sender.enviados[0]["destino"] == "caio@al.insper.edu.br"

    def test_a_senha_devolvida_e_a_que_loga(self):
        """O elo que importa: o que aparece na tela de quem cadastrou é o que
        abre a conta. Sem isto, a diretoria repassaria uma senha que não entra."""
        uc = montar_registro()

        resposta = uc.execute(PEDIDO)

        criado = uc.usuario_repository.get_by_email_insper("caio@al.insper.edu.br")
        assert verificar_senha(resposta["senha_provisoria_gerada"], criado.senha_hash)

    def test_a_senha_vai_no_corpo_do_email(self):
        uc = montar_registro()

        resposta = uc.execute(PEDIDO)

        assert resposta["senha_provisoria_gerada"] in uc.email_sender.enviados[0]["texto"]

    def test_email_que_falha_nao_derruba_o_cadastro(self):
        """SMTP fora do ar (ou nem configurado) não pode deixar o membro sem
        conta — quem cadastrou está na tela, com a senha, e repassa."""
        uc = montar_registro(falha_email=True)

        resposta = uc.execute(PEDIDO)

        assert resposta["email_enviado"] is False
        assert resposta["senha_provisoria_gerada"]
        assert uc.usuario_repository.get_by_email_insper("caio@al.insper.edu.br") is not None

    def test_email_repetido_continua_recusado(self):
        uc = montar_registro(UsuarioFake(email="caio@al.insper.edu.br"))

        with pytest.raises(RegraDeNegocioError):
            uc.execute(PEDIDO)


class TestDefinirSenha:
    def test_define_e_destrava_a_plataforma(self):
        usuario = UsuarioFake()
        usuario.senha_provisoria = True
        uc = montar_definicao(usuario)

        uc.execute(usuario, DefinirSenhaRequest(nova_senha="senha-nova-boa"))

        assert usuario.senha_provisoria is False
        assert verificar_senha("senha-nova-boa", usuario.senha_hash)

    def test_recusa_senha_curta(self):
        usuario = UsuarioFake()
        usuario.senha_provisoria = True
        uc = montar_definicao(usuario)

        with pytest.raises(RegraDeNegocioError):
            uc.execute(usuario, DefinirSenhaRequest(nova_senha="1234"))

        # Recusa não pode destravar meio caminho: a senha continua a mesma e a
        # conta continua presa à tela de definição.
        assert verificar_senha("senha-antiga-dela", usuario.senha_hash)
        assert usuario.senha_provisoria is True

    def test_recusa_repetir_a_provisoria(self):
        """Manter a senha que passou por uma caixa de entrada é justamente o
        que este fluxo existe para encerrar."""
        usuario = UsuarioFake()
        usuario.senha_hash = hash_senha("PROVISORIA-1")
        usuario.senha_provisoria = True
        uc = montar_definicao(usuario)

        with pytest.raises(RegraDeNegocioError):
            uc.execute(usuario, DefinirSenhaRequest(nova_senha="PROVISORIA-1"))

        assert usuario.senha_provisoria is True


class TestReenvio:
    def test_reemite_e_marca_de_novo(self):
        usuario = UsuarioFake()
        hash_antigo = usuario.senha_hash
        uc = montar_reenvio(usuario)

        resposta = uc.execute(usuario.id)

        assert usuario.senha_provisoria is True
        assert usuario.senha_hash != hash_antigo, "reenviar derruba a senha atual"
        assert verificar_senha(resposta["senha_provisoria_gerada"], usuario.senha_hash)

    def test_recusa_membro_desativado(self):
        """Desligado não volta pelo reenvio — seria contornar o §10."""
        usuario = UsuarioFake(ativo=False)
        uc = montar_reenvio(usuario)

        with pytest.raises(RegraDeNegocioError):
            uc.execute(usuario.id)

        assert usuario.senha_provisoria is False

    def test_usuario_inexistente_devolve_none(self):
        assert montar_reenvio().execute(99) is None

    def test_falha_de_email_ainda_devolve_a_senha(self):
        usuario = UsuarioFake()
        uc = montar_reenvio(usuario, falha_email=True)

        resposta = uc.execute(usuario.id)

        assert resposta["email_enviado"] is False
        assert verificar_senha(resposta["senha_provisoria_gerada"], usuario.senha_hash)
