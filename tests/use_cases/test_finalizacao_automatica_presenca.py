"""§8/§6.5, 2026-09-04 — a finalização automática precisa marcar presença.

⚠ Este teste existe por um bug que a suíte inteira não pegava: sem passar
`presentes`, `RegistrarRealizacaoBancaUseCase` nunca toca
`candidatura.confirmado` (ele só atualiza dentro do `if request.presentes is
not None`). Como `confirmado` nasce `False` no banco, toda banca finalizada
pelo job passaria a marcar 100% de falta para todo mundo, sempre — a tela de
Presença (`PresencaBancas.tsx`) ficaria mentindo silenciosamente. A correção
foi passar `presentes` = todo mundo que se candidatou (a mesma suposição que
o extinto `RealizarBancaModal` já usava por padrão).
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca import finalizacao_automatica as mod
from src.use_cases.banca.finalizacao_automatica import FinalizacaoAutomaticaBancaUseCase


@pytest.fixture
def uc(monkeypatch):
    """`FinalizacaoAutomaticaBancaUseCase` com os repositórios trocados por
    dublês — devolve `(instancia, chamadas)`, `chamadas` guarda o request
    que chegou em `RegistrarRealizacaoBancaUseCase.execute`."""
    chamadas = {}

    class FakeVazio:
        def __init__(self, db):
            pass

    class CandidaturaFake(FakeVazio):
        def get_by_banca(self, banca_id):
            return [SimpleNamespace(usuario_id=1), SimpleNamespace(usuario_id=2)]

    class BancaEscopoFake(FakeVazio):
        # Sem escopo vinculado: `_abrir_avaliacao_de_desempenho` sai cedo,
        # sem lote. O que este teste cobre é só a chamada de realização.
        def get_escopo_ids(self, banca_id):
            return []

    class RegistrarRealizacaoFake:
        def __init__(self, db):
            pass

        def execute(self, banca_id, request, eh_diretor_projetos=False):
            chamadas["banca_id"] = banca_id
            chamadas["request"] = request
            chamadas["eh_diretor_projetos"] = eh_diretor_projetos
            return {"id": banca_id, "realizado_em": datetime.now(), "status": "realizada"}

    for nome, fake in [
        ("BancaRepository", FakeVazio),
        ("CandidaturaRepository", CandidaturaFake),
        ("BancaEscopoRepository", BancaEscopoFake),
        ("EscopoRepository", FakeVazio),
        ("ProjetoEscopoRepository", FakeVazio),
        ("ProjetoRepository", FakeVazio),
        ("DesempenhoLoteRepository", FakeVazio),
    ]:
        monkeypatch.setattr(mod, nome, fake)
    monkeypatch.setattr(mod, "RegistrarRealizacaoBancaUseCase", RegistrarRealizacaoFake)

    return FinalizacaoAutomaticaBancaUseCase(db=None), chamadas


def test_presentes_e_todo_mundo_que_se_candidatou(uc):
    instancia, chamadas = uc
    banca = SimpleNamespace(id=42)

    instancia._processar(banca)

    assert chamadas["banca_id"] == 42
    assert sorted(chamadas["request"].presentes) == [1, 2]


def test_continua_forcando_e_como_diretor(uc):
    """As duas garantias que já existiam antes desta correção — sem
    regressão nelas."""
    instancia, chamadas = uc

    instancia._processar(SimpleNamespace(id=1))

    assert chamadas["request"].forcar is True
    assert chamadas["eh_diretor_projetos"] is True


def test_banca_sem_candidato_nenhum_manda_lista_vazia(uc):
    """Banca automática que ninguém se candidatou — não é erro, `presentes`
    só fica vazio (ninguém para confirmar)."""
    instancia, chamadas = uc
    # Sobrescreve o fake para devolver ninguém.
    instancia.candidatura_repository.get_by_banca = lambda _id: []

    instancia._processar(SimpleNamespace(id=7))

    assert chamadas["request"].presentes == []
