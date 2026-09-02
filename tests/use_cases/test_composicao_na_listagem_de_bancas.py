"""`GET /bancas` passa a devolver a composição por frente (2026-09-02).

⭐ Por que o campo existe: `piso_minimo` é uma SOMA — diz "faltam 2" e não diz
de quê. A aba Bancas precisa da quebra para dizer "falta 1 de Direito", e
calculá-la no front exigiria repetir lá a regra da liderança (vaga a mais), a
exclusão da equipe do projeto e a leitura da matriz de Configurações.

⚠ Banca LEGADA (sem frente vinculada) devolve `[]`, não erro: ela não cai em
combinação nenhuma, e a tela mostra só o teto, como sempre foi para ela.
"""

from types import SimpleNamespace

from src.use_cases.banca.get_banca import composicao_da_banca

BUSINESS, DIREITO = 1, 3


class FakeResolver:
    def __init__(self, regras):
        self._regras = regras
        self.chamadas = []

    def para(self, frente_ids):
        self.chamadas.append(list(frente_ids))
        return self._regras


class FakeChecker:
    """Devolve contagem fixa — o assunto aqui é o FORMATO da resposta; quem
    testa a contagem é `tests/utils/test_composicao_banca.py`."""

    def __init__(self, contagens):
        self._contagens = contagens
        self.candidatos = None

    def contar(self, _banca, _regras, candidato_ids):
        self.candidatos = candidato_ids
        return self._contagens


def contagem(frente_id, nome, membros, liderancas, min_membros=3, min_lideranca=1):
    return SimpleNamespace(
        frente_id=frente_id,
        frente_nome=nome,
        min_membros=min_membros,
        max_membros=99,
        min_lideranca=min_lideranca,
        max_lideranca=99,
        membros=membros,
        liderancas=liderancas,
    )


def test_devolve_uma_linha_por_frente_com_regra_e_contagem():
    banca = SimpleNamespace(id=1, coordenador_id=None)
    checker = FakeChecker(
        [
            contagem(BUSINESS, "Business", membros=1, liderancas=0),
            contagem(DIREITO, "Direito", membros=1, liderancas=1, min_membros=1),
        ]
    )
    resolver = FakeResolver(regras=[])

    composicao = composicao_da_banca(
        banca,
        [SimpleNamespace(id=BUSINESS), SimpleNamespace(id=DIREITO)],
        [10, 11, 12],
        checker,
        resolver,
    )

    assert [c["frente_nome"] for c in composicao] == ["Business", "Direito"]
    assert composicao[0]["membros"] == 1 and composicao[0]["min_membros"] == 3
    assert composicao[1]["liderancas"] == 1
    # A regra é pedida para a COMBINAÇÃO inteira, não frente a frente: é a
    # combinação que a matriz de Configurações endereça.
    assert resolver.chamadas == [[BUSINESS, DIREITO]]
    assert checker.candidatos == {10, 11, 12}


def test_banca_legada_sem_frente_devolve_lista_vazia():
    banca = SimpleNamespace(id=2, coordenador_id=None)
    resolver = FakeResolver(regras=[])

    assert composicao_da_banca(banca, [], [10], FakeChecker([]), resolver) == []
    # E nem pergunta: sem frente não há combinação a resolver.
    assert resolver.chamadas == []
