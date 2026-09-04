"""§8 — `GET /bancas/{id}/detalhes` só exige login (2026-09-04).

Quem está NA banca sempre foi informação aberta a qualquer um da casa: a
página `/bancas` já mostrava a lista corrida de avaliadores pra QUALQUER
pessoa logada, sem checagem nenhuma (via `contexto.candidaturas` +
`contexto.usuarios`, montados no cliente). Esta rota chegou a ganhar um
recorte de acesso ao projeto (§3, com exceção de avaliador escalado) — e
isso quebrou o caso comum: um avaliador sem NENHUM outro vínculo com o
projeto (o normal — §8, ninguém avalia o próprio grupo) tomava 404 na ficha
agrupada, embora a MESMA informação já estivesse visível pra ele na lista
corrida ao lado. A ficha não é dado sensível do projeto (orçamento, cliente,
proposta) — é só quem está na banca. O recorte saiu.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.routers import bancas

CONSULTOR_QUALQUER = SimpleNamespace(id=50, posicao="consultor")


class FakeGetBancaDetalhesUseCase:
    def __init__(self, db):
        pass

    def execute(self, banca_id):
        if banca_id == 999:
            return None
        return {"id": banca_id, "projeto_id": 99, "avaliadores": []}


def test_qualquer_pessoa_logada_acessa_a_ficha_mesmo_sem_vinculo_nenhum(monkeypatch):
    """O caso que estava quebrado: nem vê o projeto, nem é avaliador — só
    está logada. Isso é o suficiente."""
    monkeypatch.setattr(bancas, "GetBancaDetalhesUseCase", FakeGetBancaDetalhesUseCase)

    detalhes = bancas.get_banca_detalhes(1, current_user=CONSULTOR_QUALQUER, db=None)

    assert detalhes["id"] == 1


def test_banca_inexistente_leva_404(monkeypatch):
    monkeypatch.setattr(bancas, "GetBancaDetalhesUseCase", FakeGetBancaDetalhesUseCase)

    with pytest.raises(HTTPException) as erro:
        bancas.get_banca_detalhes(999, current_user=CONSULTOR_QUALQUER, db=None)

    assert erro.value.status_code == 404
    assert erro.value.detail == "Banca não encontrada"


def test_regressao_nao_volta_a_checar_acesso_ao_projeto(monkeypatch):
    """⭐ Se alguém reintroduzir a checagem de projeto, este teste denuncia:
    o portão (fake) aqui SEMPRE recusa, então só passa se a rota não estiver
    chamando nenhum portão de acesso."""
    monkeypatch.setattr(bancas, "GetBancaDetalhesUseCase", FakeGetBancaDetalhesUseCase)

    def recusa_sempre(*a, **k):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    monkeypatch.setattr(bancas, "exigir_acesso_ao_projeto", recusa_sempre)

    detalhes = bancas.get_banca_detalhes(1, current_user=CONSULTOR_QUALQUER, db=None)

    assert detalhes["id"] == 1
