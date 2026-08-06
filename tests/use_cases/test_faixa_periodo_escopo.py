"""⭐ A faixa que pinta o período de cada escopo no cronograma (§5.4).

Da reunião inicial (que preencheu `data_inicio`) até a banca daquele escopo —
as duas pontas que o coordenador crava. Ela é DERIVADA a cada leitura: mover a
reunião ou remarcar a banca redesenha o retângulo sozinho, e é justamente essa
propriedade que estes testes prendem.

`_faixas_derivadas` não toca em `self`, então a instância vem sem `__init__` —
mesma manha de `test_marco_sem_tarefa.py`, e pelo mesmo motivo: exercitar a
regra sem precisar de um banco.
"""

from datetime import date, datetime
from types import SimpleNamespace

from src.use_cases.cronograma.get_cronograma import GetCronogramaUseCase

CASO = GetCronogramaUseCase.__new__(GetCronogramaUseCase)

SEG_10 = date(2026, 8, 10)
SAB_22 = date(2026, 8, 22)


def projeto(kickoff=None, dias_ambientacao=0):
    return SimpleNamespace(data_kickoff=kickoff, dias_ambientacao=dias_ambientacao)


def escopo(id=1, inicio=SEG_10, entrega_real=None):
    return SimpleNamespace(id=id, data_inicio=inicio, data_entrega_real=entrega_real)


def banca(dia=SAB_22):
    return SimpleNamespace(data_hora=datetime.combine(dia, datetime.min.time()) if dia else None)


def periodos(escopos, bancas):
    faixas = CASO._faixas_derivadas(projeto(), escopos, [], bancas)
    return [f for f in faixas if f["tipo"] == "escopo"]


class TestPeriodoDoEscopo:
    def test_da_reuniao_inicial_ate_a_banca(self):
        (faixa,) = periodos([escopo()], {1: banca()})
        assert (faixa["inicio"], faixa["fim"]) == (SEG_10, SAB_22)
        assert faixa["projeto_escopo_id"] == 1

    def test_sem_reuniao_inicial_nao_ha_periodo(self):
        """Escopo não iniciado não tem janela — é o "0/12" da tabela."""
        assert periodos([escopo(inicio=None)], {1: banca()}) == []

    def test_sem_data_de_banca_nao_ha_periodo(self):
        assert periodos([escopo()], {1: banca(dia=None)}) == []
        assert periodos([escopo()], {}) == []

    def test_banca_antes_da_reuniao_vira_um_dia(self):
        """Remarcação para trás: melhor um dia do que um retângulo invertido,
        que o calendário desenharia como faixa nenhuma."""
        (faixa,) = periodos([escopo()], {1: banca(dia=date(2026, 8, 3))})
        assert (faixa["inicio"], faixa["fim"]) == (SEG_10, SEG_10)

    def test_escopos_em_paralelo_geram_duas_faixas(self):
        """§5.4 admite escopos simultâneos — cada um com a sua janela."""
        faixas = periodos(
            [escopo(id=1), escopo(id=2, inicio=date(2026, 8, 17))],
            {1: banca(), 2: banca(dia=date(2026, 9, 11))},
        )
        assert [(f["projeto_escopo_id"], f["inicio"], f["fim"]) for f in faixas] == [
            (1, SEG_10, SAB_22),
            (2, date(2026, 8, 17), date(2026, 9, 11)),
        ]

    def test_escopo_entregue_mantem_a_faixa(self):
        """A janela do escopo continua no calendário depois da entrega — é o
        histórico do que aconteceu, não um estado atual."""
        assert len(periodos([escopo(entrega_real=SAB_22)], {1: banca()})) == 1
