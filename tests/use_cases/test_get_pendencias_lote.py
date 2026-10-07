"""`GetPendenciasLoteUseCase` — cobre a Avaliação do Escopo entrando (e não
entrando) nas pendências do lote.

Antes desta correção (2026-09-24), o cálculo de pendências vinha só de
`calcular_pares_lote`, que pula avaliador == avaliado de propósito (não é
"par"). A fila PESSOAL de cada um (`get_fila.py`) já somava a Avaliação do
Escopo como item adicional há tempos, mas o painel de pendências — e as
notificações que nascem dele — nunca sabiam que ela existia: a diretoria via
"Fulano falta avaliar Beltrano" e nunca "falta avaliar Escopo", mesmo com o
lote e o formulário prontos.

2026-10-05: a periódica também pode incluir a Avaliação do Escopo, sobre
os escopos EM ANDAMENTO; e, nos dois tipos, é uma resposta POR ESCOPO, só dos
escopos da frente da pessoa (`utils/desempenho_escopo.py`).
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
AVALIACOES_RESPONDIDAS = set()  # {(lote_id, avaliador_id, avaliado_id, projeto_escopo_id|None)}
FORMULARIOS = {}  # {(tipo, papel): objeto ou None}
CRITERIOS_POR_FORMULARIO = {}  # {formulario_id: lista}
ESCOPOS = {}  # {projeto_escopo_id: SimpleNamespace(id, projeto_id, frente_id, status, escopo_id, nome_customizado)}
ESCOPOS_DA_BANCA = {}  # {banca_id: [projeto_escopo_id]}
FRENTES_POR_USUARIO = {}  # {usuario_id: {frente_id}}
CATALOGO = {}  # {escopo_id: nome}

FRENTE_BUSINESS = 1
FRENTE_DIREITO = 2


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
        return (lote_id, avaliador_id, avaliado_id, None) in AVALIACOES_RESPONDIDAS

    def respondeu_escopo(self, lote_id, usuario_id, projeto_escopo_id):
        return (lote_id, usuario_id, usuario_id, projeto_escopo_id) in AVALIACOES_RESPONDIDAS or (
            self.existe_par(lote_id, usuario_id, usuario_id)
        )


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

    def vigente(self, tipo, papel):
        return FORMULARIOS.get((tipo, papel))

    def get_by_id(self, formulario_id):
        return next((f for f in FORMULARIOS.values() if f and f.id == formulario_id), None)


class FakeDesempenhoLoteFormularioRepository:
    """Sem versão congelada em nenhum lote: tudo cai na vigente."""

    def __init__(self, db):
        pass

    def formulario_id_de(self, lote_id, papel):
        return None


class FakeDesempenhoCriterioRepository:
    def __init__(self, db):
        pass

    def get_by_formulario(self, formulario_id):
        return CRITERIOS_POR_FORMULARIO.get(formulario_id, [])


class FakeProjetoEscopoRepository:
    def __init__(self, db):
        pass

    def get_by_projetos(self, projeto_ids):
        return [e for e in ESCOPOS.values() if e.projeto_id in projeto_ids]

    def get_by_ids(self, ids):
        return [ESCOPOS[i] for i in ids if i in ESCOPOS]


class FakeBancaEscopoRepository:
    def __init__(self, db):
        pass

    def get_escopo_ids(self, banca_id):
        return ESCOPOS_DA_BANCA.get(banca_id, [])


class FakeUsuarioFrenteRepository:
    def __init__(self, db):
        pass

    def get_all(self):
        return [
            SimpleNamespace(usuario_id=uid, frente_id=fid)
            for uid, frentes in FRENTES_POR_USUARIO.items()
            for fid in frentes
        ]


class FakeEscopoRepository:
    def __init__(self, db):
        pass

    def get_by_id(self, escopo_id):
        nome = CATALOGO.get(escopo_id)
        return SimpleNamespace(id=escopo_id, nome=nome) if nome else None


def _escopo(id, projeto_id, frente_id, status="em_andamento", escopo_id=None, nome_customizado=None):
    ESCOPOS[id] = SimpleNamespace(
        id=id,
        projeto_id=projeto_id,
        frente_id=frente_id,
        status=status,
        escopo_id=escopo_id,
        nome_customizado=nome_customizado,
    )
    return ESCOPOS[id]


@pytest.fixture(autouse=True)
def _mundo(monkeypatch):
    for d in (
        LOTES,
        PROJETO_IDS_POR_LOTE,
        MEMBROS_POR_PROJETO,
        USUARIOS,
        PROJETOS,
        AVALIACOES_RESPONDIDAS,
        FORMULARIOS,
        CRITERIOS_POR_FORMULARIO,
        ESCOPOS,
        ESCOPOS_DA_BANCA,
        FRENTES_POR_USUARIO,
        CATALOGO,
    ):
        d.clear()

    modulo = "src.use_cases.desempenho_lote.get_pendencias"
    monkeypatch.setattr(f"{modulo}.DesempenhoLoteRepository", FakeDesempenhoLoteRepository)
    monkeypatch.setattr(f"{modulo}.DesempenhoLoteProjetoRepository", FakeDesempenhoLoteProjetoRepository)
    monkeypatch.setattr(f"{modulo}.ProjetoMembroRepository", FakeProjetoMembroRepository)
    monkeypatch.setattr(f"{modulo}.DesempenhoAvaliacaoRepository", FakeDesempenhoAvaliacaoRepository)
    monkeypatch.setattr(f"{modulo}.UsuarioRepository", FakeUsuarioRepository)
    monkeypatch.setattr(f"{modulo}.ProjetoRepository", FakeProjetoRepository)
    monkeypatch.setattr(f"{modulo}.DesempenhoFormularioRepository", FakeDesempenhoFormularioRepository)
    monkeypatch.setattr(f"{modulo}.DesempenhoLoteFormularioRepository", FakeDesempenhoLoteFormularioRepository)
    monkeypatch.setattr(f"{modulo}.DesempenhoCriterioRepository", FakeDesempenhoCriterioRepository)
    monkeypatch.setattr(f"{modulo}.ProjetoEscopoRepository", FakeProjetoEscopoRepository)
    monkeypatch.setattr(f"{modulo}.BancaEscopoRepository", FakeBancaEscopoRepository)
    monkeypatch.setattr(f"{modulo}.UsuarioFrenteRepository", FakeUsuarioFrenteRepository)
    monkeypatch.setattr(f"{modulo}.EscopoRepository", FakeEscopoRepository)

    PROJETOS[5] = SimpleNamespace(id=5, nome="ATLAS I")
    USUARIOS[33] = SimpleNamespace(id=33, nome="Gustavo Gazel Silva")
    USUARIOS[22] = SimpleNamespace(id=22, nome="Letícia Ortiz Napolitano")
    USUARIOS[24] = SimpleNamespace(id=24, nome="Mariana Terra Giacometti")
    MEMBROS_POR_PROJETO[5] = [
        SimpleNamespace(usuario_id=33, projeto_id=5, papel="coordenador"),
        SimpleNamespace(usuario_id=22, projeto_id=5, papel="consultor"),
        SimpleNamespace(usuario_id=24, projeto_id=5, papel="consultor"),
    ]
    for uid in (33, 22, 24):
        FRENTES_POR_USUARIO[uid] = {FRENTE_BUSINESS}
    CATALOGO[70] = "Análise Mercadológica"
    CATALOGO[71] = "Plano de Negócios"
    CATALOGO[72] = "Compliance"
    # Finalização automática: o lote nasce da banca 400, que cobriu o escopo 100.
    _escopo(100, 5, FRENTE_BUSINESS, escopo_id=70)
    ESCOPOS_DA_BANCA[400] = [100]
    LOTES[18] = SimpleNamespace(
        id=18,
        nome="Finalização - ATLAS I - Análise Mercadológica",
        tipo="finalizacao",
        banca_id=400,
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
        assert p["projeto_escopo_id"] == 100
        assert p["escopo_nome"] == "Análise Mercadológica"

    # Os pares normais continuam intactos, do jeito que já eram.
    pares = _por_form_type(resultado, "consultor") + _por_form_type(resultado, "coordenador")
    assert len(pares) == 6  # 3 pessoas, cada uma avalia as outras 2
    assert all(p["projeto_escopo_id"] is None for p in pares)


def test_marca_respondida_quando_ja_existe_a_autoavaliacao(db=None):
    AVALIACOES_RESPONDIDAS.add((18, 24, 24, 100))

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    escopo_mariana = next(p for p in resultado if p["form_type"] == "escopo" and p["avaliador_id"] == 24)
    assert escopo_mariana["respondida"] is True


def test_resposta_antiga_sem_escopo_conta_como_respondida(db=None):
    # Antes de 2026-10-05 a Avaliação do Escopo não dizia qual escopo era.
    AVALIACOES_RESPONDIDAS.add((18, 24, 24, None))

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


def test_banca_com_dois_escopos_da_mesma_frente_gera_um_item_por_escopo(db=None):
    _escopo(101, 5, FRENTE_BUSINESS, escopo_id=71)
    ESCOPOS_DA_BANCA[400] = [100, 101]

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    de_mariana = [p for p in _por_form_type(resultado, "escopo") if p["avaliador_id"] == 24]
    assert {p["projeto_escopo_id"] for p in de_mariana} == {100, 101}
    assert {p["escopo_nome"] for p in de_mariana} == {"Análise Mercadológica", "Plano de Negócios"}


def test_quem_e_de_direito_nao_avalia_o_escopo_de_business(db=None):
    USUARIOS[50] = SimpleNamespace(id=50, nome="Pessoa de Direito")
    MEMBROS_POR_PROJETO[5].append(SimpleNamespace(usuario_id=50, projeto_id=5, papel="consultor"))
    FRENTES_POR_USUARIO[50] = {FRENTE_DIREITO}
    _escopo(102, 5, FRENTE_DIREITO, escopo_id=72)
    ESCOPOS_DA_BANCA[400] = [100, 102]

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    escopos = _por_form_type(resultado, "escopo")
    de_direito = [p["projeto_escopo_id"] for p in escopos if p["avaliador_id"] == 50]
    de_business = [p["projeto_escopo_id"] for p in escopos if p["avaliador_id"] == 24]
    assert de_direito == [102]
    assert de_business == [100]


def test_sem_frente_cadastrada_avalia_todos_os_escopos_do_projeto(db=None):
    del FRENTES_POR_USUARIO[24]
    _escopo(102, 5, FRENTE_DIREITO, escopo_id=72)
    ESCOPOS_DA_BANCA[400] = [100, 102]

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    de_mariana = [p["projeto_escopo_id"] for p in _por_form_type(resultado, "escopo") if p["avaliador_id"] == 24]
    assert sorted(de_mariana) == [100, 102]


# ---------------------------------------------------------------- periódica


def _virar_periodico(com_formulario=True):
    LOTES[18].tipo = "periodico"
    LOTES[18].banca_id = None
    ESCOPOS_DA_BANCA.clear()
    if com_formulario:
        FORMULARIOS[("periodico", "escopo")] = SimpleNamespace(id=9)
        CRITERIOS_POR_FORMULARIO[9] = [SimpleNamespace(id=7)]


def test_periodico_inclui_escopo_em_andamento_e_ignora_o_nao_iniciado(db=None):
    _virar_periodico()
    _escopo(101, 5, FRENTE_BUSINESS, status="nao_iniciado", escopo_id=71)

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    escopos = _por_form_type(resultado, "escopo")
    assert {p["avaliador_id"] for p in escopos} == {33, 22, 24}
    assert {p["projeto_escopo_id"] for p in escopos} == {100}


def test_periodico_nao_inclui_escopo_sem_escopo_em_andamento(db=None):
    _virar_periodico()
    # Um ainda não começou, o outro já foi entregue: nada pra avaliar agora.
    ESCOPOS[100].status = "nao_iniciado"
    _escopo(101, 5, FRENTE_BUSINESS, status="entregue", escopo_id=71)

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    assert _por_form_type(resultado, "escopo") == []


def test_periodico_dois_escopos_em_andamento_da_mesma_frente_sao_duas_respostas(db=None):
    _virar_periodico()
    _escopo(101, 5, FRENTE_BUSINESS, escopo_id=71)

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    de_mariana = [p["projeto_escopo_id"] for p in _por_form_type(resultado, "escopo") if p["avaliador_id"] == 24]
    assert sorted(de_mariana) == [100, 101]


def test_periodico_so_conta_os_projetos_com_escopo_em_andamento(db=None):
    _virar_periodico()
    PROJETOS[6] = SimpleNamespace(id=6, nome="BLEND I")
    USUARIOS[40] = SimpleNamespace(id=40, nome="Fulano")
    MEMBROS_POR_PROJETO[6] = [SimpleNamespace(usuario_id=40, projeto_id=6, papel="consultor")]
    FRENTES_POR_USUARIO[40] = {FRENTE_BUSINESS}
    PROJETO_IDS_POR_LOTE[18] = [5, 6]
    _escopo(200, 6, FRENTE_BUSINESS, status="nao_iniciado", escopo_id=70)

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    escopos = _por_form_type(resultado, "escopo")
    assert {p["avaliador_id"] for p in escopos} == {33, 22, 24}
    assert 40 not in {p["avaliador_id"] for p in escopos}


def test_periodico_usa_o_proprio_formulario_e_nao_o_da_finalizacao(db=None):
    # Só o `(finalizacao, escopo)` existe com conteúdo; o da periódica, não.
    _virar_periodico(com_formulario=False)

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    assert _por_form_type(resultado, "escopo") == []


def test_periodico_respeita_a_escolha_de_nao_incluir(db=None):
    _virar_periodico()
    LOTES[18].inclui_avaliacao_de_escopo = False

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    assert _por_form_type(resultado, "escopo") == []


def test_escopo_outro_usa_o_nome_digitado(db=None):
    _virar_periodico()
    ESCOPOS[100].escopo_id = None
    ESCOPOS[100].nome_customizado = "Diagnóstico especial"

    resultado = GetPendenciasLoteUseCase(db).execute(18)

    assert {p["escopo_nome"] for p in _por_form_type(resultado, "escopo")} == {"Diagnóstico especial"}
