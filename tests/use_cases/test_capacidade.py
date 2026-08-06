"""Capacidade por frente (§7.3): quantos projetos ainda cabem.

A conta é `max(0, teto − projetos da pessoa)`, somada por frente e por papel.

⭐ **O `max(0)` é o coração disto.** Um consultor com 3 projetos está
sobrecarregado, mas isso NÃO tira do núcleo a chance de vender para outra
pessoa. Sem o corte em zero ele contribuiria −1 e cancelaria a vaga livre de um
colega — a tela diria que não dá para vender quando dá.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.monitoramento.monitoramento import (
    TETO_POR_PAPEL,
    AlocacaoUseCase,
)


def linha(usuario_id, nome, total):
    return {"usuario_id": usuario_id, "nome": nome, "total": total}


class FakeFrentes:
    def __init__(self, frentes):
        self._frentes = frentes

    def get_all(self):
        return [SimpleNamespace(id=i, nome=n) for i, n in self._frentes.items()]


class FakeVinculos:
    def __init__(self, pares):
        self._pares = pares

    def get_all(self):
        return [SimpleNamespace(usuario_id=u, frente_id=f) for u, f in self._pares]


def montar(frentes=None, vinculos=()):
    uc = AlocacaoUseCase.__new__(AlocacaoUseCase)
    uc.frente_repository = FakeFrentes(frentes or {1: "Business", 2: "Tech"})
    uc.usuario_frente_repository = FakeVinculos(vinculos)
    return uc


class TestSobrecargaNaoVicaNegativa:
    @pytest.mark.parametrize("projetos,esperado", [(0, 2), (1, 1), (2, 0), (3, 0), (9, 0)])
    def test_consultor(self, projetos, esperado):
        uc = montar()
        r = uc._capacidade([], [linha(1, "Ana", projetos)])
        assert r["total"]["consultor"] == esperado

    @pytest.mark.parametrize("projetos,esperado", [(0, 4), (3, 1), (4, 0), (7, 0)])
    def test_coordenador(self, projetos, esperado):
        uc = montar()
        r = uc._capacidade([linha(1, "Ana", projetos)], [])
        assert r["total"]["coordenador"] == esperado

    def test_sobrecarregado_nao_cancela_a_vaga_do_colega(self):
        """O caso que o `max(0)` protege: sem ele daria 2 − 1 = 1, e a tela
        diria que só cabe um projeto quando cabem dois."""
        uc = montar()
        r = uc._capacidade([], [linha(1, "Livre", 0), linha(2, "Lotado", 3)])
        assert r["total"]["consultor"] == 2


class TestAgrupamentoPorFrente:
    def test_soma_por_frente(self):
        uc = montar(vinculos=[(1, 1), (2, 1), (3, 2)])
        r = uc._capacidade([], [linha(1, "A", 0), linha(2, "B", 1), linha(3, "C", 0)])
        por_nome = {l["frente_nome"]: l for l in r["por_frente"]}
        assert por_nome["Business"]["consultor"] == 3   # 2 + 1
        assert por_nome["Tech"]["consultor"] == 2

    def test_os_dois_papeis_ficam_separados(self):
        """Nunca somados: converter em "projetos vendáveis" exigiria assumir o
        tamanho da equipe, e a suposição sumiria dentro do número."""
        uc = montar(vinculos=[(1, 1), (2, 1)])
        uc_r = uc._capacidade([linha(2, "Coord", 0)], [linha(1, "Cons", 0)])
        linha_business = uc_r["por_frente"][0]
        assert linha_business["consultor"] == 2
        assert linha_business["coordenador"] == 4

    def test_quem_nao_tem_frente_vira_linha_propria(self):
        """Some faria a soma das frentes não bater com o total, sem nada na
        tela explicando a diferença."""
        uc = montar(vinculos=[(1, 1)])
        r = uc._capacidade([], [linha(1, "Com", 0), linha(2, "Sem", 0)])
        nomes = [l["frente_nome"] for l in r["por_frente"]]
        assert "Sem frente" in nomes

    def test_sem_frente_vai_por_ultimo_mesmo_tendo_mais_vagas(self):
        """Hoje ela junta os diretores, que não têm projeto. No topo, diria que
        a maior oportunidade do núcleo está fora de qualquer frente."""
        uc = montar(vinculos=[(1, 1)])
        r = uc._capacidade([], [linha(1, "Com", 2), linha(2, "SemA", 0), linha(3, "SemB", 0)])
        assert r["por_frente"][-1]["frente_nome"] == "Sem frente"

    def test_mais_capacidade_primeiro_entre_as_frentes(self):
        uc = montar(vinculos=[(1, 1), (2, 2)])
        r = uc._capacidade([], [linha(1, "A", 2), linha(2, "B", 0)])
        assert r["por_frente"][0]["frente_nome"] == "Tech"


class TestTotalNaoEhSomaDasLinhas:
    def test_pessoa_em_duas_frentes_conta_uma_vez_no_total(self):
        """⭐ Ela aparece nas duas linhas — está nas duas frentes de verdade —
        mas a vaga dela é UMA. Somar as linhas contaria duas vezes e prometeria
        capacidade que não existe."""
        uc = montar(vinculos=[(1, 1), (1, 2)])
        r = uc._capacidade([], [linha(1, "Dupla", 0)])

        soma_das_linhas = sum(l["consultor"] for l in r["por_frente"])
        assert soma_das_linhas == 4        # aparece em Business e em Tech
        assert r["total"]["consultor"] == 2  # mas só há 2 vagas de verdade


class TestTetoNaResposta:
    def test_o_teto_vai_junto_para_a_tela_poder_explicar(self):
        """Sem ele a tela escreveria "2" e "4" por conta própria, e as duas
        pontas divergiriam na primeira mudança."""
        uc = montar()
        assert uc._capacidade([], [])["teto"] == TETO_POR_PAPEL
