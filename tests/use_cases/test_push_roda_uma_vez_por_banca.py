"""2026-09-16, a pedido — o rodízio marca `push_executado_em` em TODA banca
que avalia nesta passada, escale alguém ou não. É essa marca (lida por
`BancaRepository.get_por_periodo`, testado à parte) que garante a banca
nunca mais voltar pro push — nem que a diretoria descubra o piso de novo
depois. Aqui o que se prende é só a ORQUESTRAÇÃO de `execute()`: quem chama
`_processar_banca` e quem marca, não a regra de composição em si (essa já
tem os próprios testes em `test_push_composicao_por_frente.py`).
"""

from types import SimpleNamespace

from src.use_cases.banca.push_alocacao_automatica import PushAlocacaoAutomaticaUseCase


class FakeBancaRepo:
    def __init__(self, bancas):
        self._bancas = bancas
        self.marcadas = []

    def get_por_periodo(self, inicio, fim):
        return self._bancas

    def update(self, banca_id, **kwargs):
        self.marcadas.append((banca_id, kwargs))


def _uc(monkeypatch, *, bancas, resultados_por_banca):
    """`resultados_por_banca`: {banca_id: dict|None} — o que `_processar_banca`
    devolveria pra cada uma, dublê pra não reimplementar a regra de
    composição aqui."""
    uc = PushAlocacaoAutomaticaUseCase.__new__(PushAlocacaoAutomaticaUseCase)
    banca_repo = FakeBancaRepo(bancas)
    uc.banca_repository = banca_repo
    uc.configuracao_repository = SimpleNamespace(get=lambda: SimpleNamespace(vagas_por_banca=5))
    uc.candidatura_repository = SimpleNamespace(contagem_bancas_por_usuario=lambda: {})
    monkeypatch.setattr(
        uc,
        "_processar_banca",
        lambda banca, teto, contagem: resultados_por_banca.get(banca.id),
    )
    return uc, banca_repo


def _banca(id):
    return SimpleNamespace(id=id)


def test_marca_toda_banca_mesmo_quando_nao_escala_ninguem(monkeypatch):
    """O caso central: piso já coberto, `_processar_banca` devolve None (não
    escalou ninguém) — mesmo assim a banca é marcada, porque a AVALIAÇÃO
    aconteceu, só não precisou de ninguém novo."""
    uc, banca_repo = _uc(
        monkeypatch,
        bancas=[_banca(1)],
        resultados_por_banca={1: None},
    )

    resumo = uc.execute()

    assert resumo == []
    assert len(banca_repo.marcadas) == 1
    banca_id, kwargs = banca_repo.marcadas[0]
    assert banca_id == 1
    assert kwargs["push_executado_em"] is not None


def test_marca_banca_que_escalou_gente_tambem(monkeypatch):
    uc, banca_repo = _uc(
        monkeypatch,
        bancas=[_banca(1)],
        resultados_por_banca={1: {"banca_id": 1, "usuarios_alocados": [7]}},
    )

    resumo = uc.execute()

    assert len(resumo) == 1
    assert len(banca_repo.marcadas) == 1


def test_marca_cada_banca_da_passada_independentemente(monkeypatch):
    uc, banca_repo = _uc(
        monkeypatch,
        bancas=[_banca(1), _banca(2), _banca(3)],
        resultados_por_banca={1: None, 2: {"banca_id": 2, "usuarios_alocados": [9]}, 3: None},
    )

    uc.execute()

    ids_marcados = {banca_id for banca_id, _ in banca_repo.marcadas}
    assert ids_marcados == {1, 2, 3}


def test_sem_banca_nenhuma_nao_marca_nada(monkeypatch):
    uc, banca_repo = _uc(monkeypatch, bancas=[], resultados_por_banca={})

    assert uc.execute() == []
    assert banca_repo.marcadas == []
