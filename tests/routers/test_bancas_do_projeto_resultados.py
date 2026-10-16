"""`GET /projetos/{id}/bancas`: quem lê as avaliações com nome, sem nome ou
nem lê (2026-10-16, a pedido).

A aba Banca do projeto recebia a ficha inteira, com o nome de cada avaliador,
pra qualquer um com acesso ao projeto: o front só não desenhava. Agora a rota
decide pelo leitor: Dashboard de Bancas vê com nome; quem é do projeto vê
notas e comentários sem autor; o visitante (avaliador escalado, sem outro
vínculo) não vê resultado nenhum.
"""

from types import SimpleNamespace

import pytest

from src.routers import projetos

LEITOR = SimpleNamespace(id=50, posicao="consultor")


def ficha(banca_id):
    return {
        "id": banca_id,
        "nota_final": 4.5,
        "avaliadores": [
            {"usuario_id": 7, "nome": "Ana", "ja_enviou": True, "comentario_feedback": "da Ana"},
            {"usuario_id": 50, "nome": "Eu", "ja_enviou": True, "comentario_feedback": "meu"},
        ],
        "avaliacoes": [
            {"id": 900 + banca_id, "avaliador": "Ana", "avaliador_id": 7, "sessao": 1, "comentario_feedback": "da Ana", "submetida_em": "2026-10-10", "notas": []},
        ],
        "avaliacoes_anonimas": False,
    }


class FakeLista:
    def __init__(self, db):
        pass

    def execute(self, projeto_id):
        return [ficha(1), ficha(2)]


@pytest.fixture(autouse=True)
def _mundo(monkeypatch):
    monkeypatch.setattr(projetos, "ListBancasDoProjetoUseCase", FakeLista)
    monkeypatch.setattr(projetos, "usuario_tem_permissao", lambda *a, **k: False)
    monkeypatch.setattr(projetos, "exigir_acesso_a_banca_do_projeto", lambda *a, **k: False)


def test_quem_e_do_projeto_le_sem_autor():
    bancas = projetos.list_bancas_do_projeto(1, current_user=LEITOR, db=None)

    assert len(bancas) == 2
    for b in bancas:
        assert b["avaliacoes_anonimas"] is True
        assert b["nota_final"] == 4.5
        assert b["avaliacoes"] == [
            {"id": 1, "avaliador": None, "avaliador_id": None, "sessao": 1, "comentario_feedback": "da Ana", "submetida_em": None, "notas": []}
        ]
        por_id = {a["usuario_id"]: a for a in b["avaliadores"]}
        assert por_id[7]["comentario_feedback"] is None
        assert por_id[50]["comentario_feedback"] == "meu"


def test_quem_tem_o_dashboard_le_com_nome(monkeypatch):
    monkeypatch.setattr(projetos, "usuario_tem_permissao", lambda *a, **k: True)

    bancas = projetos.list_bancas_do_projeto(1, current_user=LEITOR, db=None)

    assert bancas[0]["avaliacoes_anonimas"] is False
    assert bancas[0]["avaliacoes"][0]["avaliador"] == "Ana"
    assert bancas[0]["avaliadores"][0]["comentario_feedback"] == "da Ana"


def test_visitante_nao_le_resultado_nenhum(monkeypatch):
    monkeypatch.setattr(projetos, "exigir_acesso_a_banca_do_projeto", lambda *a, **k: True)

    bancas = projetos.list_bancas_do_projeto(1, current_user=LEITOR, db=None)

    for b in bancas:
        assert b["avaliacoes"] == []
        assert b["nota_final"] is None
        assert b["avaliacoes_anonimas"] is False
        por_id = {a["usuario_id"]: a for a in b["avaliadores"]}
        assert por_id[7]["comentario_feedback"] is None
        assert por_id[50]["comentario_feedback"] == "meu", "o próprio voto continua aparecendo pra quem o deu"
