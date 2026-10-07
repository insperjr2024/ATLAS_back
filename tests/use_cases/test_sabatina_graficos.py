"""`GetGraficosEleicaoUseCase`: o que a diretoria vê da corrida e da apuração
é sempre agregado. Voto anônimo (2026-10-07): nada que saia daqui pode dizer
quem votou em quem."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.sabatina.eleicoes import GetGraficosEleicaoUseCase
from src.utils.exceptions import RegraDeNegocioError


class FakeRepo:
    def __init__(self, itens):
        self._itens = list(itens)

    def get_all(self):
        return self._itens

    def get_by_id(self, id):
        return next((i for i in self._itens if i.id == id), None)

    def get_by_eleicao(self, eleicao_id):
        return [i for i in self._itens if i.eleicao_id == eleicao_id]


USUARIOS = [
    SimpleNamespace(id=1, nome="Ana", posicao="consultor", status="ativo"),
    SimpleNamespace(id=2, nome="Bia", posicao="consultor", status="ativo"),
    SimpleNamespace(id=3, nome="Caio", posicao="gerente", status="ativo"),
    SimpleNamespace(id=4, nome="Dani", posicao="diretor_projetos", status="ativo"),
    SimpleNamespace(id=9, nome="Candidata", posicao="coordenador", status="ativo"),
]
ELEICAO = SimpleNamespace(
    id=5, nome="Diretoria", percentual_aprovacao=50, status="aberta",
    eleitores_ids=[1, 2, 3, 4], aberta_em=datetime(2026, 10, 7, 10), fechada_em=None,
)
CANDIDATOS = [SimpleNamespace(id=50, eleicao_id=5, usuario_id=9)]
VOTOS = [
    SimpleNamespace(id=1, eleicao_id=5, eleitor_id=1, candidato_id=50, peso=1, posicao="consultor",
                    criado_em=datetime(2026, 10, 7, 10, 5)),
    SimpleNamespace(id=2, eleicao_id=5, eleitor_id=3, candidato_id=None, peso=2, posicao="gerente",
                    criado_em=datetime(2026, 10, 7, 10, 1)),
]


@pytest.fixture
def uc():
    instancia = GetGraficosEleicaoUseCase.__new__(GetGraficosEleicaoUseCase)
    instancia.db = object()
    instancia.eleicao_repo = FakeRepo([ELEICAO])
    instancia.candidato_repo = FakeRepo(CANDIDATOS)
    instancia.voto_repo = FakeRepo(VOTOS)
    instancia.usuario_repo = FakeRepo(USUARIOS)
    return instancia


def _chaves(obj, acumulado=None):
    acumulado = acumulado if acumulado is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            acumulado.add(k)
            _chaves(v, acumulado)
    elif isinstance(obj, list):
        for v in obj:
            _chaves(v, acumulado)
    return acumulado


def test_nao_vaza_eleitor(uc):
    """A garantia da anonimidade: nenhuma chave da resposta aponta pra quem
    votou, e a linha do tempo não traz a posição de quem votou."""
    r = uc.execute(5)
    chaves = _chaves(r)
    assert not {"eleitor_id", "eleitor_nome", "eleitor"} & chaves
    assert all(set(e) == {"em", "candidato_id", "peso"} for e in r["linha_do_tempo"])


def test_parcial_usa_a_mesma_conta_da_apuracao(uc):
    r = uc.execute(5)
    assert r["parcial"]["total_votos"] == 2
    assert r["parcial"]["total_ponderado"] == 3
    candidata = r["parcial"]["candidatos"][0]
    assert candidata["nome"] == "Candidata"
    assert candidata["ponderado"] == 1
    assert r["parcial"]["brancos"]["ponderado"] == 2


def test_participacao_por_posicao_so_conta(uc):
    r = uc.execute(5)
    por = {f["posicao"]: f for f in r["por_posicao"]}
    assert por["consultor"] == {"posicao": "consultor", "total": 2, "votaram": 1}
    assert por["gerente"] == {"posicao": "gerente", "total": 1, "votaram": 1}
    assert por["diretor_projetos"] == {"posicao": "diretor_projetos", "total": 1, "votaram": 0}


def test_linha_do_tempo_em_ordem_cronologica(uc):
    r = uc.execute(5)
    assert [e["candidato_id"] for e in r["linha_do_tempo"]] == [None, 50]


def test_rascunho_nao_tem_grafico(uc):
    uc.eleicao_repo = FakeRepo([SimpleNamespace(**{**vars(ELEICAO), "status": "rascunho"})])
    with pytest.raises(RegraDeNegocioError):
        uc.execute(5)
