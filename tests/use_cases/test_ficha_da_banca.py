"""A ficha da banca (`GET /bancas/{id}/detalhes`) — os nomes já resolvidos.

O que estes testes protegem é a diferença entre esta ficha e a composição que
a tela `/bancas` faz do lado do cliente:

- **`membros` vem da equipe REAL do projeto**, não só da tabela legada
  `equipe_projeto`. Banca marcada pelo cronograma não escreve naquela tabela,
  e quem lê só ela mostra "Membros —" justamente nas bancas do fluxo novo.
- **O coordenador não aparece duas vezes.** Ele tem linha própria na ficha, e
  `membros_da_banca` o inclui no conjunto por outro motivo (§8: quem não pode
  avaliar).

Mesmo idioma dos outros testes de use case: dublês à mão, classes de
repositório trocadas no módulo via `monkeypatch`, porque o use case as
instancia por dentro.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca import get_banca_detalhes
from src.use_cases.banca.get_banca_detalhes import GetBancaDetalhesUseCase

BANCA = SimpleNamespace(
    id=35,
    nome_projeto="TX1",
    escopo_id=None,
    coordenador_id=90,
    data_hora=datetime(2026, 9, 8, 17, 0),
    realizado_em=None,
    resultado=None,
    descricao_coordenador=None,
)

USUARIOS = {
    90: SimpleNamespace(id=90, nome="Coordenador Tech"),
    91: SimpleNamespace(id=91, nome="Mateus Loureiro"),
    92: SimpleNamespace(id=92, nome="Bia Martins"),
}


@pytest.fixture
def mundo(monkeypatch):
    """Monta a banca e o que gira em volta dela.

    `equipe_legada` é o que a tabela `equipe_projeto` tem; `membros_projeto` é
    a equipe de verdade do projeto. A ficha deve enxergar as duas.
    """

    def _mundo(
        *,
        banca=BANCA,
        escopos=((7, 43, "Elaboração Contratual", None),),
        frentes=("Tech",),
        equipe_legada=(),
        membros_projeto=(91,),
        candidaturas=(),
    ):
        class BancaFake:
            def __init__(self, db): pass
            def get_by_id(self, banca_id):
                return banca if banca and banca_id == banca.id else None

        class BancaEscopoFake:
            def __init__(self, db): pass
            def get_escopo_ids(self, banca_id):
                return [e[0] for e in escopos]

        class ProjetoEscopoFake:
            def __init__(self, db): pass
            def get_by_id(self, escopo_id):
                for eid, projeto_id, customizado, catalogo_id in escopos:
                    if eid == escopo_id:
                        return SimpleNamespace(
                            id=eid,
                            projeto_id=projeto_id,
                            nome_customizado=customizado,
                            escopo_id=catalogo_id,
                        )
                return None

        class CatalogoFake:
            def __init__(self, db): pass
            def get_by_id(self, escopo_id):
                return SimpleNamespace(id=escopo_id, nome="Plano Financeiro")

        class BancaFrenteFake:
            def __init__(self, db): pass
            def get_by_banca(self, banca_id):
                return [SimpleNamespace(frente_id=i) for i, _ in enumerate(frentes)]

        class FrenteFake:
            def __init__(self, db): pass
            def get_by_id(self, frente_id):
                return SimpleNamespace(id=frente_id, nome=frentes[frente_id])

        class CandidaturaFake:
            def __init__(self, db): pass
            def get_by_banca(self, banca_id):
                return [SimpleNamespace(usuario_id=u) for u in candidaturas]

        class EquipeProjetoFake:
            def __init__(self, db): pass
            def get_by_banca(self, banca_id):
                return [SimpleNamespace(usuario_id=u) for u in equipe_legada]

        class ProjetoMembroFake:
            def __init__(self, db): pass
            def get_by_projeto(self, projeto_id, apenas_atuais=False):
                return [SimpleNamespace(usuario_id=u) for u in membros_projeto]

        class UsuarioFake:
            def __init__(self, db): pass
            def get_by_id(self, usuario_id):
                return USUARIOS.get(usuario_id)

        for nome, dublê in (
            ("BancaRepository", BancaFake),
            ("BancaEscopoRepository", BancaEscopoFake),
            ("ProjetoEscopoRepository", ProjetoEscopoFake),
            ("EscopoRepository", CatalogoFake),
            ("BancaFrenteRepository", BancaFrenteFake),
            ("FrenteRepository", FrenteFake),
            ("CandidaturaRepository", CandidaturaFake),
            ("EquipeProjetoRepository", EquipeProjetoFake),
            ("ProjetoMembroRepository", ProjetoMembroFake),
            ("UsuarioRepository", UsuarioFake),
        ):
            monkeypatch.setattr(get_banca_detalhes, nome, dublê)

        return GetBancaDetalhesUseCase(db=None)

    return _mundo


def test_banca_inexistente_devolve_none(mundo):
    assert mundo(banca=None).execute(35) is None


def test_resolve_os_nomes_da_ficha(mundo):
    ficha = mundo(candidaturas=(92,)).execute(35)

    assert ficha["nome_projeto"] == "TX1"
    assert ficha["coordenador"] == "Coordenador Tech"
    assert ficha["escopos"] == ["Elaboração Contratual"]
    assert ficha["frentes"] == ["Tech"]
    assert ficha["avaliadores"] == ["Bia Martins"]
    # Para a tela poder voltar ao projeto de onde a banca é.
    assert ficha["projeto_id"] == 43


def test_membros_saem_da_equipe_do_projeto_sem_linha_legada(mundo):
    """⭐ O caso do fluxo novo: banca marcada pelo cronograma.

    `equipe_projeto` fica vazia — é a tabela do módulo antigo, preenchida à
    mão. Ler só ela mostrava "Membros —" e escondia a equipe inteira.
    """
    ficha = mundo(equipe_legada=(), membros_projeto=(91,)).execute(35)

    assert ficha["membros"] == ["Mateus Loureiro"]


def test_a_equipe_legada_tambem_conta(mundo):
    """As duas fontes valem — banca antiga não pode perder a equipe dela."""
    ficha = mundo(equipe_legada=(92,), membros_projeto=()).execute(35)

    assert ficha["membros"] == ["Bia Martins"]


def test_o_coordenador_nao_se_repete_em_membros(mundo):
    """Ele tem linha própria; `membros_da_banca` o inclui por outro motivo."""
    ficha = mundo(membros_projeto=(90, 91)).execute(35)

    assert ficha["coordenador"] == "Coordenador Tech"
    assert ficha["membros"] == ["Mateus Loureiro"]


def test_escopo_do_catalogo_usa_o_nome_do_catalogo(mundo):
    """Escopo "Outro" tem `nome_customizado`; o do catálogo, não."""
    ficha = mundo(escopos=((7, 43, None, 4),)).execute(35)

    assert ficha["escopos"] == ["Plano Financeiro"]


def test_banca_legada_sem_escopo_nao_tem_projeto(mundo):
    """Sem escopo vinculado não há projeto de onde derivar acesso — e a rota
    trata isso deixando passar com o login só."""
    ficha = mundo(escopos=()).execute(35)

    assert ficha["escopos"] == []
    assert ficha["projeto_id"] is None
