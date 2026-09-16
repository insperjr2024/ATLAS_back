"""Renomear cargo (2026-09-16, a pedido): só o RÓTULO (`nome`) muda — o slug
(`posicao`, a chave que `usuario.posicao`/`cargo_extra` referenciam) nunca é
tocado aqui. Os 6 cargos padrão (`e_padrao=True`) não podem ser renomeados:
dezenas de regras hardcoded em `middlewares/authorization.py` e afins contam
com o RÓTULO deles continuar óbvio pra quem administra a plataforma."""

from types import SimpleNamespace

import pytest

from src.use_cases.posicao_permissao.update_posicao_permissao import (
    UpdatePosicaoPermissaoRequest,
    UpdatePosicaoPermissaoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


def _uc(monkeypatch, *, registro):
    caso = UpdatePosicaoPermissaoUseCase(db=None)
    estado = {"gravou": None}

    def _update(posicao, **dados):
        estado["gravou"] = (posicao, dados)
        for chave, valor in dados.items():
            setattr(registro, chave, valor)
        return registro

    caso.repository = SimpleNamespace(get_by_posicao=lambda p: registro, get_all=lambda: [registro], update=_update)
    caso.usuario_repository = SimpleNamespace(get_por_posicoes=lambda *p: [])
    monkeypatch.setattr(
        "src.use_cases.posicao_permissao.update_posicao_permissao.serializar_posicao_permissao",
        lambda r: {"posicao": r.posicao, "nome": r.nome},
    )
    return caso, estado


def test_renomeia_cargo_criado_pela_tela(monkeypatch):
    registro = SimpleNamespace(posicao="vendas", nome="Vendas", e_padrao=False, pode_administrar_permissoes=False)
    caso, estado = _uc(monkeypatch, registro=registro)

    resultado = caso.execute("vendas", UpdatePosicaoPermissaoRequest(nome="Comercial"))

    assert estado["gravou"] == ("vendas", {"nome": "Comercial"})
    assert resultado["nome"] == "Comercial"


def test_recusa_renomear_cargo_padrao(monkeypatch):
    registro = SimpleNamespace(posicao="coordenador", nome="Coordenador(a)", e_padrao=True, pode_administrar_permissoes=False)
    caso, estado = _uc(monkeypatch, registro=registro)

    with pytest.raises(RegraDeNegocioError, match="padrão"):
        caso.execute("coordenador", UpdatePosicaoPermissaoRequest(nome="Chefe"))

    assert estado["gravou"] is None


def test_recusa_nome_em_branco(monkeypatch):
    registro = SimpleNamespace(posicao="vendas", nome="Vendas", e_padrao=False, pode_administrar_permissoes=False)
    caso, estado = _uc(monkeypatch, registro=registro)

    with pytest.raises(RegraDeNegocioError):
        caso.execute("vendas", UpdatePosicaoPermissaoRequest(nome="   "))

    assert estado["gravou"] is None


def test_nao_mexe_no_slug_so_no_rotulo(monkeypatch):
    """A FK que `usuario.posicao` segue é `posicao` (o slug), não `nome` — só
    o rótulo pode mudar, o valor que outras tabelas referenciam fica intacto."""
    registro = SimpleNamespace(posicao="vendas", nome="Vendas", e_padrao=False, pode_administrar_permissoes=False)
    caso, estado = _uc(monkeypatch, registro=registro)

    caso.execute("vendas", UpdatePosicaoPermissaoRequest(nome="Comercial"))

    assert "posicao" not in estado["gravou"][1]
    assert registro.posicao == "vendas"
