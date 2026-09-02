"""As caixas de `posicao_permissao` não podem divergir entre modelo, leitura e
escrita.

O `serializar_posicao_permissao` já avisa no docstring: "num lugar só — a lista
e o update devolvem a mesma forma, senão uma permissão nova nasce faltando em
metade das telas". Isto aqui é a rede que faz o aviso valer.

⭐ **Os testes leem as colunas do MODELO, não uma lista escrita à mão.** Uma
lista fixa aqui teria o mesmo defeito que ela previne: quem adiciona a caixa
15 e esquece do serializer também esqueceria de atualizar a lista, e a suíte
passaria verde. Perguntando ao `__table__`, a caixa nova entra no teste
sozinha.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import Boolean

from src.middlewares import authorization
from src.models.posicao_permissao_model import PosicaoPermissaoModel
from src.use_cases.posicao_permissao.get_posicao_permissao import (
    serializar_posicao_permissao,
)
from src.use_cases.posicao_permissao.update_posicao_permissao import (
    UpdatePosicaoPermissaoRequest,
)


def caixas_do_modelo():
    """Toda coluna booleana de `posicao_permissao` — isto é "uma caixa"."""
    return sorted(
        coluna.name
        for coluna in PosicaoPermissaoModel.__table__.columns
        if isinstance(coluna.type, Boolean)
    )


def registro_falso(**ligadas):
    """Uma linha da tabela, com todas as caixas desligadas menos as pedidas."""
    valores = {caixa: False for caixa in caixas_do_modelo()}
    valores.update(ligadas)
    return SimpleNamespace(posicao="coordenador", **valores)


class TestSerializacao:
    def test_serializer_devolve_todas_as_caixas_do_modelo(self):
        """A que pega a caixa nova esquecida na leitura: sem ela, a tela de
        Configurações nem desenha o toggle, e o AuthContext lê `undefined`."""
        saida = serializar_posicao_permissao(registro_falso())
        faltando = set(caixas_do_modelo()) - set(saida)
        assert faltando == set(), f"caixas fora do serializer: {sorted(faltando)}"

    def test_serializer_nao_inventa_campo_que_nao_existe(self):
        """O outro lado: campo no serializer sem coluna no banco explodiria
        em runtime, não na suíte."""
        saida = serializar_posicao_permissao(registro_falso())
        sobrando = set(saida) - set(caixas_do_modelo()) - {"posicao"}
        assert sobrando == set(), f"campos sem coluna: {sorted(sobrando)}"

    def test_update_aceita_todas_as_caixas(self):
        """A que pega a caixa nova esquecida na ESCRITA: o toggle aparece na
        tela, a pessoa clica, o Pydantic descarta o campo em silêncio
        (`exclude_unset`) e nada é gravado."""
        campos = set(UpdatePosicaoPermissaoRequest.model_fields)
        faltando = set(caixas_do_modelo()) - campos
        assert faltando == set(), f"caixas que o update ignora: {sorted(faltando)}"

    def test_update_so_manda_o_que_veio(self):
        """`exclude_unset` é o que permite a tela salvar UMA caixa sem zerar as
        outras 13 — mexer nisso apagaria permissão sem ninguém pedir."""
        pedido = UpdatePosicaoPermissaoRequest(pode_ver_dashboard_bancas=True)
        assert pedido.model_dump(exclude_unset=True) == {
            "pode_ver_dashboard_bancas": True
        }


class TestGuardaDoDashboard:
    """A caixa nova precisa BARRAR de verdade, não só aparecer na tela."""

    @pytest.fixture
    def com_permissoes(self, monkeypatch):
        def _montar(registro):
            class RepositorioFake:
                def __init__(self, db):
                    pass

                def get_by_posicao(self, posicao):
                    return registro

            monkeypatch.setattr(
                authorization, "PosicaoPermissaoRepository", RepositorioFake
            )

        return _montar

    def test_caixa_ligada_passa(self, com_permissoes):
        com_permissoes(registro_falso(pode_ver_dashboard_bancas=True))
        usuario = SimpleNamespace(id=5, posicao="coordenador")
        assert (
            authorization.usuario_tem_permissao(
                usuario, db=None, campo="pode_ver_dashboard_bancas"
            )
            is True
        )

    def test_caixa_desligada_da_403(self, com_permissoes):
        """⭐ Sem esta checagem a caixa seria decorativa: o front esconderia o
        menu e a rota continuaria respondendo a quem chamasse direto."""
        com_permissoes(registro_falso())
        usuario = SimpleNamespace(id=5, posicao="coordenador")
        with pytest.raises(HTTPException) as erro:
            authorization._exigir_permissao(
                usuario, None, "pode_ver_dashboard_bancas", "sem permissão"
            )
        assert erro.value.status_code == 403

    def test_posicao_sem_linha_nao_estoura(self, com_permissoes):
        """`get_by_posicao` devolvendo `None` é possível (posição sem linha) e
        tem de significar "não pode", nunca `AttributeError`."""
        com_permissoes(None)
        usuario = SimpleNamespace(id=5, posicao="coordenador")
        assert (
            authorization.usuario_tem_permissao(
                usuario, db=None, campo="pode_ver_dashboard_bancas"
            )
            is False
        )
