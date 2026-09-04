"""§8 — `GET /bancas/{id}/detalhes` libera quem vê o projeto OU quem é
avaliador escalado na banca (2026-09-04, o bug em si).

Antes a rota usava `exigir_acesso_ao_projeto` sozinho — só `pode_ver_projeto`,
o recorte de visão do projeto. Um avaliador comum não é da equipe do próprio
projeto por definição (§8: ninguém avalia o próprio grupo), então tomava 404
exatamente na tela onde mais se abre esta rota: o "ver mais" da página
`/bancas`, e a ficha agrupada da aba Banca do projeto. A correção troca pro
mesmo portão que `GET /projetos/{id}` já usa pra aba Banca
(`exigir_acesso_a_banca_do_projeto`), que libera pelas duas portas.

Mesmo padrão de `tests/routers/test_acesso_banca.py`: monkeypatch no módulo
`bancas`, onde a rota importou os nomes.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.routers import bancas

CONSULTOR = SimpleNamespace(id=50, posicao="consultor")


class FakeGetBancaDetalhesUseCase:
    def __init__(self, db):
        pass

    def execute(self, banca_id):
        return {"id": banca_id, "projeto_id": 99, "avaliadores": []}


class FakeGetBancaDetalhesUseCaseSemProjeto:
    """Banca legada, sem escopo vinculado — `projeto_id` nulo."""

    def __init__(self, db):
        pass

    def execute(self, banca_id):
        return {"id": banca_id, "projeto_id": None, "avaliadores": []}


def test_avaliador_escalado_sem_ver_o_projeto_acessa_a_ficha(monkeypatch):
    """O caso que estava quebrado: avaliador sem nenhum outro vínculo com o
    projeto que a banca pertence."""
    monkeypatch.setattr(bancas, "GetBancaDetalhesUseCase", FakeGetBancaDetalhesUseCase)
    monkeypatch.setattr(
        bancas, "exigir_acesso_a_banca_do_projeto", lambda *a, **k: True
    )

    detalhes = bancas.get_banca_detalhes(1, current_user=CONSULTOR, db=None)

    assert detalhes["id"] == 1


def test_quem_nao_ve_o_projeto_nem_e_avaliador_leva_404(monkeypatch):
    monkeypatch.setattr(bancas, "GetBancaDetalhesUseCase", FakeGetBancaDetalhesUseCase)

    def recusa(projeto_id, current_user, db):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    monkeypatch.setattr(bancas, "exigir_acesso_a_banca_do_projeto", recusa)

    with pytest.raises(HTTPException) as erro:
        bancas.get_banca_detalhes(1, current_user=CONSULTOR, db=None)

    assert erro.value.status_code == 404


def test_banca_legada_sem_projeto_nao_checa_acesso_nenhum(monkeypatch):
    monkeypatch.setattr(bancas, "GetBancaDetalhesUseCase", FakeGetBancaDetalhesUseCaseSemProjeto)

    def estoura_se_chamado(*a, **k):
        raise AssertionError("não deveria checar acesso a projeto nenhum")

    monkeypatch.setattr(bancas, "exigir_acesso_a_banca_do_projeto", estoura_se_chamado)

    detalhes = bancas.get_banca_detalhes(1, current_user=CONSULTOR, db=None)

    assert detalhes["id"] == 1


def test_regressao_nao_volta_a_usar_o_portao_so_de_projeto(monkeypatch):
    """⭐ A regressão em si: se alguém trocar de volta pro
    `exigir_acesso_ao_projeto` puro (sem a exceção de avaliador), este teste
    denuncia — o portão antigo aqui SEMPRE recusa, então só passa se a rota
    estiver chamando o novo."""
    monkeypatch.setattr(bancas, "GetBancaDetalhesUseCase", FakeGetBancaDetalhesUseCase)
    monkeypatch.setattr(
        bancas, "exigir_acesso_a_banca_do_projeto", lambda *a, **k: True
    )

    def portao_antigo_recusa(*a, **k):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    monkeypatch.setattr(bancas, "exigir_acesso_ao_projeto", portao_antigo_recusa)

    detalhes = bancas.get_banca_detalhes(1, current_user=CONSULTOR, db=None)

    assert detalhes["id"] == 1
