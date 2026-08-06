"""O §3 nas rotas que agem sobre UMA banca.

Estas rotas nasceram protegidas só por `require_pode_definir_cronograma`, que
olha o CARGO e não o escopo. O efeito era concreto: uma coordenadora que recebe
404 ao abrir `GET /projetos/13` conseguia mesmo assim realizar, aprovar e apagar
a banca daquele projeto — e aprovar banca é o que libera a entrega ao cliente
(§5.5). O teste abaixo é a rede que impede isso de voltar.

Os repositórios são importados DENTRO de `_exigir_acesso_a_banca`, então os
dublês precisam trocar a classe no módulo de origem, não em `bancas`.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.repositories import banca_escopo_repository, projeto_escopo_repository
from src.routers import bancas

COORDENADORA_DO_ALFA = SimpleNamespace(id=7, posicao="coordenador")


@pytest.fixture
def banco(monkeypatch):
    """Monta o mundo: quais escopos cada banca cobre, de que projeto é cada
    escopo, e quais projetos o usuário enxerga."""

    def _banco(*, escopos_da_banca, projeto_do_escopo, projetos_visiveis):
        class BancaEscopoFake:
            def __init__(self, db): pass
            def get_escopo_ids(self, banca_id):
                return escopos_da_banca.get(banca_id, [])

        class ProjetoEscopoFake:
            def __init__(self, db): pass
            def get_by_id(self, escopo_id):
                projeto_id = projeto_do_escopo.get(escopo_id)
                return SimpleNamespace(projeto_id=projeto_id) if projeto_id else None

        def exigir_acesso_fake(projeto_id, current_user, db):
            if projeto_id not in projetos_visiveis:
                raise HTTPException(status_code=404, detail="Projeto não encontrado")

        monkeypatch.setattr(banca_escopo_repository, "BancaEscopoRepository", BancaEscopoFake)
        monkeypatch.setattr(projeto_escopo_repository, "ProjetoEscopoRepository", ProjetoEscopoFake)
        monkeypatch.setattr(bancas, "exigir_acesso_ao_projeto", exigir_acesso_fake)

    return _banco


def test_banca_de_projeto_alheio_da_404(banco):
    """⭐ O furo em si: cargo certo, projeto errado."""
    banco(
        escopos_da_banca={12: [30]},
        projeto_do_escopo={30: 13},   # banca 12 é do Beta
        projetos_visiveis={1},        # ela só enxerga o Alfa
    )
    with pytest.raises(HTTPException) as erro:
        bancas._exigir_acesso_a_banca(12, COORDENADORA_DO_ALFA, db=None)

    assert erro.value.status_code == 404, "tem de ser 404 — 403 confirmaria que a banca existe"


def test_banca_do_proprio_projeto_passa(banco):
    banco(
        escopos_da_banca={5: [10]},
        projeto_do_escopo={10: 1},
        projetos_visiveis={1},
    )
    bancas._exigir_acesso_a_banca(5, COORDENADORA_DO_ALFA, db=None)


def test_banca_legada_sem_escopo_continua_administravel(banco):
    """Banca cadastrada antes de `banca_escopo` existir não tem projeto de onde
    tirar a regra. Bloqueá-la deixaria o legado inadministrável."""
    banco(escopos_da_banca={9: []}, projeto_do_escopo={}, projetos_visiveis=set())
    bancas._exigir_acesso_a_banca(9, COORDENADORA_DO_ALFA, db=None)


def test_banca_de_varios_escopos_exige_acesso_a_todos(banco):
    """Uma banca pode cobrir N escopos (§8, "uma data só"). Enxergar um dos
    projetos não pode dar direito de aprovar a banca do outro junto."""
    banco(
        escopos_da_banca={7: [10, 30]},
        projeto_do_escopo={10: 1, 30: 13},
        projetos_visiveis={1},
    )
    with pytest.raises(HTTPException) as erro:
        bancas._exigir_acesso_a_banca(7, COORDENADORA_DO_ALFA, db=None)

    assert erro.value.status_code == 404


def test_banca_inexistente_nao_estoura_antes_do_use_case(banco):
    """Sem vínculo nenhum, o guard sai limpo e quem responde 404 é o use case —
    a mensagem certa é "Banca não encontrada", não "Projeto não encontrado"."""
    banco(escopos_da_banca={}, projeto_do_escopo={}, projetos_visiveis={1})
    bancas._exigir_acesso_a_banca(9999, COORDENADORA_DO_ALFA, db=None)
