"""⭐ A faixa que pinta a JANELA de cada escopo no cronograma (§5, §7).

⚠ **Esta faixa mudou de significado.** Antes ela ia da reunião inicial até a
*data da banca*, e por isso sumia enquanto a banca não tivesse data — justo
quando ela é mais útil, que é na hora de decidir onde a banca cabe.

Agora ela é a janela: da reunião inicial até *vendidos + ajustados* dias úteis
depois dela. É **previsão**, não consequência — a banca precisa caber dentro
dela (§9), não o contrário.

Ela continua DERIVADA a cada leitura: mover a reunião inicial ou aprovar dias
de ajuste redesenha o retângulo sozinho, e é essa propriedade que estes testes
prendem.

`_faixas_derivadas` não toca em `self`, então a instância vem sem `__init__` —
mesma manha de `test_marco_sem_tarefa.py`.
"""

from datetime import date
from types import SimpleNamespace

from src.use_cases.cronograma.get_cronograma import GetCronogramaUseCase

CASO = GetCronogramaUseCase.__new__(GetCronogramaUseCase)

SEG_10_08 = date(2026, 8, 10)
#: 10 dias úteis a partir de 10/08 (sem feriado no meio) fecham em 21/08.
SEX_21_08 = date(2026, 8, 21)
#: Com +5 ajustados, vão até 28/08.
SEX_28_08 = date(2026, 8, 28)


def projeto(kickoff=None, dias_ambientacao=0, inicio_ambientacao=None):
    return SimpleNamespace(
        data_kickoff=kickoff,
        dias_ambientacao=dias_ambientacao,
        data_inicio_ambientacao=inicio_ambientacao,
    )


def escopo(id=1, inicio=SEG_10_08, entrega_real=None, vendidos=10, ajustados=0):
    return SimpleNamespace(
        id=id,
        data_inicio=inicio,
        data_entrega_real=entrega_real,
        dias_uteis_vendidos=vendidos,
        dias_uteis_ajustados=ajustados,
    )


def janelas(escopos, calendario=()):
    faixas = CASO._faixas_derivadas(projeto(), escopos, list(calendario))
    return [f for f in faixas if f["tipo"] == "escopo"]


class TestJanelaDoEscopo:
    def test_da_reuniao_inicial_ate_o_fim_dos_dias_vendidos(self):
        (faixa,) = janelas([escopo()])

        assert (faixa["inicio"], faixa["fim"]) == (SEG_10_08, SEX_21_08)
        assert faixa["projeto_escopo_id"] == 1

    def test_dias_ajustados_esticam_a_faixa(self):
        """⭐ Aprovar +5 redesenha o retângulo — sem ninguém regravar nada."""
        (faixa,) = janelas([escopo(ajustados=5)])

        assert faixa["fim"] == SEX_28_08

    def test_o_rotulo_mostra_vendidos_e_ajustados_separados(self):
        """A tela nunca diz "15 vendidos": diz 10 vendidos + 5 ajustados."""
        (faixa,) = janelas([escopo(ajustados=5)])

        assert faixa["rotulo"] == "Janela do escopo (10 vendidos + 5 ajustados)"

    def test_sem_ajuste_o_rotulo_nao_polui(self):
        (faixa,) = janelas([escopo()])

        assert faixa["rotulo"] == "Janela do escopo (10 vendidos)"

    def test_sem_reuniao_inicial_nao_ha_janela(self):
        """§20.4: escopo não iniciado não tem janela — é o "0/12" da tabela."""
        assert janelas([escopo(inicio=None)]) == []

    def test_a_faixa_existe_mesmo_sem_banca_marcada(self):
        """⭐ A regressão que motivou a mudança: a janela é previsão e não
        depende da banca. Antes, escopo sem banca não tinha faixa nenhuma."""
        assert len(janelas([escopo()])) == 1

    def test_feriado_no_meio_empurra_o_fim_da_janela(self):
        """A janela é contada em dias ÚTEIS, como todo o resto do sistema."""
        (faixa,) = janelas([escopo()], calendario=[date(2026, 8, 12)])

        assert faixa["fim"] == date(2026, 8, 24)

    def test_escopos_em_paralelo_geram_duas_faixas(self):
        """§5.4 admite escopos simultâneos — cada um com a sua janela."""
        faixas = janelas([escopo(id=1), escopo(id=2, inicio=date(2026, 8, 17), vendidos=5)])

        assert [(f["projeto_escopo_id"], f["inicio"], f["fim"]) for f in faixas] == [
            (1, SEG_10_08, SEX_21_08),
            (2, date(2026, 8, 17), date(2026, 8, 21)),
        ]

    def test_escopo_entregue_mantem_a_faixa(self):
        """A janela continua no calendário depois da entrega — é o histórico do
        que foi prometido, não um estado atual."""
        assert len(janelas([escopo(entrega_real=SEX_21_08)])) == 1
