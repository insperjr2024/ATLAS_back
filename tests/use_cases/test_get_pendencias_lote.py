"""`GetPendenciasLoteUseCase` — cobre a Avaliação do Escopo entrando (e não
entrando) nas pendências do lote.

Antes desta correção (2026-09-24), o cálculo de pendências vinha só de
`calcular_pares_lote`, que pula avaliador == avaliado de propósito (não é
"par"). A fila PESSOAL de cada um (`get_fila.py`) já somava a Avaliação do
Escopo como item adicional há tempos, mas o painel de pendências — e as
notificações que nascem dele — nunca sabiam que ela existia: a diretoria via
"Fulano falta avaliar Beltrano" e nunca "falta avaliar Escopo", mesmo com o
lote e o formulário prontos.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.desempenho_lote.get_pendencias import GetPendenciasLoteUseCase

LOTES = {}
PROJETO_IDS_POR_LOTE = {}
MEMBROS_POR_PROJETO = {}
USUARIOS = {}
PROJETOS = {}
AVALIACOES_RESPONDIDAS = set()  # {(lote_id, avaliador_id, avaliado_id)}
FORMULARIOS = {}  # {(tipo, papel): objeto ou None}
CRITERIOS_POR_FORMULARIO = {}  # {formulario_id: lista}


class FakeDesempenhoLoteRepository:
    def __init__(self, db):
        pass

    def get_by_id(self, lote_id):
        return LOTES.get(lote_id)


class FakeDesempenhoLoteProjetoRepository:
    def __init__(self, db):
        pass

    def get_projeto_ids(self, lote_id):
        return PROJETO_IDS_POR_LOTE.get(lote_id, [])


class FakeProjetoMembroRepository:
    def __init__(self, db):
        pass

    def get_by_projetos(self, projeto_ids, apenas_atuais=True):
        return [m for pid in projeto_ids for m in MEMBROS_POR_PROJETO.get(pid, [])]


class FakeDesempenhoAvaliacaoRepository:
    def __init__(self, db):
        pass

    def existe_par(self, lote_id, avaliador_id, avaliado_id):
        return (lote_id, avaliador_id, avaliado_id) in AVALIACOES_RESPONDIDAS


class FakeUsuarioRepository:
    def __init__(self, db):
        pass

    def get_all(self):
        return list(USUARIOS.values())


class FakeProjetoRepository:
    def __init__(self, db):
        pass

    def get_all(self):
        return list(PROJETOS.values())


class FakeDesempenhoFormularioRepository:
    def __init__(self, db):
        pass

    def first_by(self, tipo, papel):
        return FORMULARIOS.get((tipo, papel))


class FakeDesempenhoCriterioRepository:
    def __init__(self, db):
        pass

    def get_by_formulario(self, formulario_id):
        return CRITERIOS_POR_FORMULARIO.get(formulario_id, [])


@pytest.fixture(autouse=True)
def _mundo(monkeypatch):
    LOTES.clear()
    PROJETO_IDS_POR_LOTE.clear()
    MEMBROS_POR_PROJETO.clear()
    USUARIOS.clear()
    PROJETOS.clear()
    AVALIACOES_RESPONDIDAS.clear()
    FORMULARIOS.clear()
    CRITERIOS_POR_FORMULARIO.clear()

    modulo = "src.use_cases.desempenho_lote.get_pendencias"
    monkeypatch.setattr(f"{modulo}.DesempenhoLoteRepository", FakeDesempenhoLoteRepository)
    monkeypatch.setattr(f"{modulo}.DesempenhoLoteProjetoRepository", FakeDesempenhoLoteProjetoRepository)
    monkeypatch.setattr(f"{modulo}.ProjetoMembroRepository", FakeProjetoMembroRepository)
    monkeypatch.setattr(f"{modulo}.DesempenhoAvaliacaoRepository", FakeDesempenhoAvaliacaoRepository)
    monkeypatch.setattr(f"{modulo}.UsuarioRepository", FakeUsuarioRepository)
    monkeypatch.setattr(f"{modulo}.ProjetoRepository", FakeProjetoRepository)
    monkeypatch.setattr(f"{modulo}.DesempenhoFormularioRepository", FakeDesempenhoFormularioRepository)
    monkeypatch.setattr(f"{modulo}.DesempenhoCriterioRepository", FakeDesempenhoCriterioRepository)

    PROJETOS[5] = SimpleNamespace(id=5, nome="ATLAS I")
    USUARIOS[33] = SimpleNamespace(id=33, nome="Gustavo Gazel Silva")
    USUARIOS[22] = SimpleNamespace(id=22, nome="Letícia Ortiz Napolitano")
    USUARIOS[24] = SimpleNamespace(id=24, nome="Mariana Terra Giacometti")
    MEMBROS_POR_PROJETO[5] = [
        SimpleNamespace(usuario_id=33, projeto_id=5, papel="coordenador"),
        SimpleNamespace(usuario_id=22, projeto_id=5, papel="consultor"),
        SimpleNamespace(usuario_id=24, projeto_id=5, papel="consultor"),
    ]
    LOTES[18] = SimpleNamespace(
        id=18,
        nome="Finalização - ATLAS I - Análise Mercadológica",
        tipo="finalizacao",
        criado_em=datetime(2026, 9, 15, 22, 0),
        inclui_avaliacao_de_escopo=True,
    )
    PROJETO_IDS_POR_LOTE[18] = [5]
    FORMULARIOS[("finalizacao", "escopo")] = SimpleNamespace(id=5)
    CRITERIOS_POR_FORMULARIO[5] = [SimpleNamespace(id=1), SimpleNamespace(id=2)]


def _por_form_type(pendencias, form_type):
    return [p for p in pendencias if p["form_type"] == form_type]


def test_inclui_avaliacao_do_escopo_pra_cada_membro_do_projeto(db=None):
    resultado = GetPendenciasLoteUseCase(db).execute(18)

    escopos = _por_form_type(resultado, "escopo")
    assert {p["avaliador_id"] for p in escopos} == {33, 22, 24}
    for p in escopos:
        assert p["avaliado_id"] == p["avaliador_id"]
        assert p["respondida"] is False
        assert p["projeto_ids"] == [5]

    # Os pares normais continuam intactos, do jeito que já eram.
    pares = _por_form_type(resultado, "consultor") + _por_form_type(resultado, "coordenador")
    assert len(pares) == 6  # 3 pessoas, cada uma avalia as outras 2


def test_marca_respondida_quando_ja_existe_a_autoavaliacao(db=None):
    AVALIACOES_RESPONDIDAS.add((18, 24, 24))

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    escopo_mariana = next(p for p in resultado if p["form_type"] == "escopo" and p["avaliador_id"] == 24)
    assert escopo_mariana["respondida"] is True


def test_nao_inclui_escopo_quando_lote_nao_tem_a_avaliacao_ativada(db=None):
    LOTES[18].inclui_avaliacao_de_escopo = False

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    assert _por_form_type(resultado, "escopo") == []


def test_nao_inclui_escopo_quando_formulario_ainda_nao_tem_criterios(db=None):
    CRITERIOS_POR_FORMULARIO[5] = []

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    assert _por_form_type(resultado, "escopo") == []


def test_nao_inclui_escopo_em_lote_periodico(db=None):
    LOTES[18].tipo = "periodico"

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    assert _por_form_type(resultado, "escopo") == []
