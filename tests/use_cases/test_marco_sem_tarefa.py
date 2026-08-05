"""De onde parte a contagem de "sem tarefa nova" (§7.2).

O marco tem duas origens possíveis — a última tarefa criada ou o kickoff — e o
TIPO vai para a resposta da API porque o front precisa escrever "desde o
kickoff" ou "desde a última tarefa" e não consegue deduzir isso do número de
dias. Antes ele deduzia pelo `sem_tarefas`, o que acertava por coincidência.
Estes testes prendem a regra para a coincidência não voltar a ser a garantia.
"""

from datetime import date, datetime
from types import SimpleNamespace

from src.use_cases.monitoramento.monitoramento import ExecucaoUseCase

# Setembro de 2026: 11 é sexta, 14 segunda, 15 terça, 18 sexta.
SEX_11 = date(2026, 9, 11)
SEG_14 = date(2026, 9, 14)
TER_15 = date(2026, 9, 15)
SEX_18 = date(2026, 9, 18)

# `_marco_sem_tarefa` e `_dias_uteis_sem_tarefa` não tocam em `self`; instanciar
# sem `__init__` evita precisar de um banco só para exercitar a regra.
CASO = ExecucaoUseCase.__new__(ExecucaoUseCase)


def projeto(kickoff=None):
    return SimpleNamespace(data_kickoff=kickoff)


def tarefa(criada_em=None):
    return SimpleNamespace(
        criado_em=datetime.combine(criada_em, datetime.min.time()) if criada_em else None
    )


class TestMarcoSemTarefa:
    def test_sem_tarefa_o_marco_e_o_kickoff(self):
        assert CASO._marco_sem_tarefa(projeto(SEX_11), []) == (SEX_11, "kickoff")

    def test_sem_tarefa_e_sem_kickoff_nao_ha_marco(self):
        """A execução não começou (§5.2) — não há o que cobrar ainda."""
        assert CASO._marco_sem_tarefa(projeto(None), []) == (None, None)

    def test_com_tarefa_o_marco_e_a_mais_recente(self):
        tarefas = [tarefa(SEX_11), tarefa(TER_15), tarefa(SEG_14)]
        assert CASO._marco_sem_tarefa(projeto(None), tarefas) == (TER_15, "ultima_tarefa")

    def test_a_tarefa_ganha_do_kickoff(self):
        """Com tarefa criada, o relógio reinicia nela, não no kickoff."""
        marco, tipo = CASO._marco_sem_tarefa(projeto(SEX_11), [tarefa(SEG_14)])
        assert (marco, tipo) == (SEG_14, "ultima_tarefa")

    def test_tarefa_sem_data_de_criacao_e_ignorada(self):
        tarefas = [tarefa(None), tarefa(SEG_14)]
        assert CASO._marco_sem_tarefa(projeto(SEX_11), tarefas) == (SEG_14, "ultima_tarefa")

    def test_so_tarefas_sem_data_caem_no_kickoff(self):
        assert CASO._marco_sem_tarefa(projeto(SEX_11), [tarefa(None)]) == (SEX_11, "kickoff")


class TestDiasUteisSemTarefa:
    def test_sem_marco_devolve_none(self):
        assert CASO._dias_uteis_sem_tarefa(None, SEG_14, []) is None

    def test_marco_hoje_ainda_nao_conta(self):
        assert CASO._dias_uteis_sem_tarefa(SEG_14, SEG_14, []) == 0

    def test_marco_no_futuro_nao_conta(self):
        assert CASO._dias_uteis_sem_tarefa(SEX_18, SEG_14, []) == 0

    def test_fim_de_semana_nao_conta(self):
        assert CASO._dias_uteis_sem_tarefa(SEX_11, SEG_14, []) == 1
        assert (SEG_14 - SEX_11).days == 3

    def test_dia_nao_letivo_no_meio_nao_conta(self):
        assert CASO._dias_uteis_sem_tarefa(SEG_14, SEX_18, [TER_15]) == 3

    def test_none_e_zero_sao_situacoes_diferentes(self):
        """`None` = sem kickoff; `0` = tem marco, mas nenhum dia útil passou.

        A tela trata os dois de forma distinta ("sem kickoff" contra a
        contagem), então colapsá-los apagaria informação.
        """
        assert CASO._dias_uteis_sem_tarefa(None, SEG_14, []) is None
        assert CASO._dias_uteis_sem_tarefa(SEG_14, SEG_14, []) == 0
