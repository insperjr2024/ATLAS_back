"""A passagem de bastão da diretoria e a trava que impede a plataforma de
ficar sem ninguém capaz de administrá-la."""

import pytest

from src.use_cases.usuario.transferir_diretoria import (
    TransferirDiretoriaRequest,
    TransferirDiretoriaUseCase,
)
from src.use_cases.usuario.update_usuario import UpdateUsuarioRequest, UpdateUsuarioUseCase
from src.utils.exceptions import RegraDeNegocioError


class UsuarioFake:
    def __init__(self, id, nome, posicao, status="ativo"):
        self.id = id
        self.nome = nome
        self.posicao = posicao
        self.status = status
        self.ativo = status == "ativo"
        self.email_insper = f"{nome.split()[0].lower()}@al.insper.edu.br"
        self.cargo_id = 4
        self.coordenador_vendas = False
        self.semestre_graduacao = None
        # Diretor em exercício já fez o primeiro acesso — `serializar_usuario`
        # devolve este campo desde que a senha provisória passou a existir.
        self.senha_provisoria = False
        self.foto = None


class UsuarioRepositoryFake:
    def __init__(self, *usuarios):
        self._por_id = {u.id: u for u in usuarios}

    def get_by_id(self, usuario_id):
        return self._por_id.get(usuario_id)

    def get_por_posicao(self, posicao):
        return [u for u in self._por_id.values() if u.posicao == posicao]

    def update(self, usuario_id, **campos):
        usuario = self._por_id.get(usuario_id)
        if not usuario:
            return None
        for chave, valor in campos.items():
            setattr(usuario, chave, valor)
        return usuario


class SemestreRepositoryFake:
    def get_ativo(self):
        return None


class DbFake:
    def __init__(self):
        self.adicionados = []
        self.commits = 0

    def add(self, registro):
        self.adicionados.append(registro)

    def commit(self):
        self.commits += 1


def montar_transferencia(*usuarios):
    uc = TransferirDiretoriaUseCase.__new__(TransferirDiretoriaUseCase)
    uc.db = DbFake()
    uc.repository = UsuarioRepositoryFake(*usuarios)
    uc.semestre_repository = SemestreRepositoryFake()
    return uc


def montar_update(*usuarios):
    uc = UpdateUsuarioUseCase.__new__(UpdateUsuarioUseCase)
    uc.db = DbFake()
    uc.repository = UsuarioRepositoryFake(*usuarios)
    uc.semestre_repository = SemestreRepositoryFake()
    uc.membro_repository = type("R", (), {"contar_ativos_por_usuario": lambda self: {}})()
    return uc


class TestTransferirDiretoria:
    def test_promove_a_nova_e_a_anterior_vira_ex_membro(self):
        dani = UsuarioFake(1, "Dani Alves", "diretor_projetos")
        ana = UsuarioFake(2, "Ana Souza", "coordenador")
        uc = montar_transferencia(dani, ana)

        uc.execute(TransferirDiretoriaRequest(novo_diretor_id=2, diretor_atual_id=1, posicao="diretor_projetos"), alterado_por=99)

        assert ana.posicao == "diretor_projetos"
        assert dani.status == "ex_membro"

    def test_quem_sai_perde_o_acesso_na_hora(self):
        """`get_current_user` recusa quem não está ativo — o token da pessoa
        que saiu para de valer no request seguinte."""
        dani = UsuarioFake(1, "Dani Alves", "diretor_projetos")
        uc = montar_transferencia(dani, UsuarioFake(2, "Ana Souza", "coordenador"))

        uc.execute(TransferirDiretoriaRequest(novo_diretor_id=2, diretor_atual_id=1, posicao="diretor_projetos"))

        assert dani.ativo is False

    def test_a_posicao_de_quem_sai_nao_e_reescrita(self):
        """§10: o arquivo tem que continuar mostrando que ela FOI diretora."""
        dani = UsuarioFake(1, "Dani Alves", "diretor_projetos")
        uc = montar_transferencia(dani, UsuarioFake(2, "Ana Souza", "coordenador"))

        uc.execute(TransferirDiretoriaRequest(novo_diretor_id=2, diretor_atual_id=1, posicao="diretor_projetos"))

        assert dani.posicao == "diretor_projetos"

    def test_sobra_exatamente_uma_diretoria_ativa(self):
        """A pessoa que entra é promovida antes de a que sai ser desligada."""
        dani = UsuarioFake(1, "Dani Alves", "diretor_projetos")
        ana = UsuarioFake(2, "Ana Souza", "coordenador")
        uc = montar_transferencia(dani, ana)

        uc.execute(TransferirDiretoriaRequest(novo_diretor_id=2, diretor_atual_id=1, posicao="diretor_projetos"))

        ativos = [u.nome for u in uc.repository.get_por_posicao("diretor_projetos") if u.status == "ativo"]
        assert ativos == ["Ana Souza"]

    def test_registra_a_promocao_no_historico(self):
        dani = UsuarioFake(1, "Dani Alves", "diretor_projetos")
        ana = UsuarioFake(2, "Ana Souza", "coordenador")
        uc = montar_transferencia(dani, ana)

        uc.execute(TransferirDiretoriaRequest(novo_diretor_id=2, diretor_atual_id=1, posicao="diretor_projetos"), alterado_por=99)

        registrados = [(h.usuario_id, h.posicao, h.alterado_por) for h in uc.db.adicionados]
        assert registrados == [(2, "diretor_projetos", 99)]

    def test_transferir_para_si_mesmo_e_recusado(self):
        dani = UsuarioFake(1, "Dani Alves", "diretor_projetos")
        uc = montar_transferencia(dani)
        with pytest.raises(RegraDeNegocioError, match="pessoa diferente"):
            uc.execute(TransferirDiretoriaRequest(novo_diretor_id=1, diretor_atual_id=1, posicao="diretor_projetos"))

    def test_quem_nao_e_diretor_hoje_nao_pode_passar_o_bastao(self):
        gil = UsuarioFake(1, "Gil Nunes", "gerente")
        ana = UsuarioFake(2, "Ana Souza", "coordenador")
        uc = montar_transferencia(gil, ana)
        with pytest.raises(RegraDeNegocioError, match="não ocupa"):
            uc.execute(TransferirDiretoriaRequest(novo_diretor_id=2, diretor_atual_id=1, posicao="diretor_projetos"))

    def test_cada_diretoria_passa_o_proprio_bastao(self):
        """A `posicao` da request escolhe QUAL diretoria troca de mão.

        Sem isso, a divisão em três cargos teria deixado a rota passando
        sempre a de projetos — a diretora de gestão de pessoas trocaria de
        mão por edição solta na tela, que é justamente o que este caso de uso
        existe para evitar.
        """
        duda = UsuarioFake(1, "Duda Passos", "diretor_pessoas")
        ana = UsuarioFake(2, "Ana Souza", "coordenador")
        uc = montar_transferencia(duda, ana)

        uc.execute(
            TransferirDiretoriaRequest(
                novo_diretor_id=2, diretor_atual_id=1, posicao="diretor_pessoas"
            )
        )

        assert ana.posicao == "diretor_pessoas"
        assert duda.status == "ex_membro"

    def test_nao_passa_uma_diretoria_que_a_pessoa_nao_ocupa(self):
        """Quem é diretor de projetos não passa a diretoria de pessoas.

        Os cargos são independentes: aceitar aqui promoveria alguém a um
        cargo que a pessoa que "passou" nunca teve para dar.
        """
        vidda = UsuarioFake(1, "Vidda Rodrigues", "diretor_projetos")
        ana = UsuarioFake(2, "Ana Souza", "coordenador")
        uc = montar_transferencia(vidda, ana)

        with pytest.raises(RegraDeNegocioError, match="não ocupa"):
            uc.execute(
                TransferirDiretoriaRequest(
                    novo_diretor_id=2, diretor_atual_id=1, posicao="diretor_pessoas"
                )
            )

    @pytest.mark.parametrize("status", ["ex_membro", "desligado"])
    def test_nao_entrega_a_diretoria_a_quem_nao_esta_ativo(self, status):
        dani = UsuarioFake(1, "Dani Alves", "diretor_projetos")
        edu = UsuarioFake(2, "Edu Prado", "consultor", status=status)
        uc = montar_transferencia(dani, edu)
        with pytest.raises(RegraDeNegocioError, match="não está ativo"):
            uc.execute(TransferirDiretoriaRequest(novo_diretor_id=2, diretor_atual_id=1, posicao="diretor_projetos"))
        assert edu.posicao == "consultor"


class TestTravaDoUltimoDiretor:
    """Só a diretoria edita cargos e permissões — rebaixar o último diretor
    trancaria a administração sem ninguém capaz de destrancar."""

    def test_rebaixar_o_ultimo_diretor_e_bloqueado(self):
        uc = montar_update(UsuarioFake(1, "Dani Alves", "diretor_projetos"))
        with pytest.raises(RegraDeNegocioError, match="última pessoa na diretoria"):
            uc.execute(1, UpdateUsuarioRequest(posicao="gerente"))

    def test_desativar_o_ultimo_diretor_e_bloqueado(self):
        uc = montar_update(UsuarioFake(1, "Dani Alves", "diretor_projetos"))
        with pytest.raises(RegraDeNegocioError, match="última pessoa na diretoria"):
            uc.execute(1, UpdateUsuarioRequest(status="ex_membro"))

    def test_rebaixar_havendo_outro_diretor_e_permitido(self):
        dani = UsuarioFake(1, "Dani Alves", "diretor_projetos")
        uc = montar_update(dani, UsuarioFake(9, "Admin", "diretor_projetos"))
        uc.execute(1, UpdateUsuarioRequest(posicao="gerente"))
        assert dani.posicao == "gerente"

    def test_outro_diretor_inativo_nao_conta_como_reserva(self):
        uc = montar_update(
            UsuarioFake(1, "Dani Alves", "diretor_projetos"),
            UsuarioFake(9, "Admin", "diretor_projetos", status="ex_membro"),
        )
        with pytest.raises(RegraDeNegocioError, match="última pessoa na diretoria"):
            uc.execute(1, UpdateUsuarioRequest(posicao="gerente"))

    def test_editar_outro_campo_do_ultimo_diretor_continua_livre(self):
        dani = UsuarioFake(1, "Dani Alves", "diretor_projetos")
        uc = montar_update(dani)
        uc.execute(1, UpdateUsuarioRequest(cargo_id=3))
        assert dani.posicao == "diretor_projetos"
