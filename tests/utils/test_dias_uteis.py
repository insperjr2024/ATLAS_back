"""Os casos que o briefing (§5.4) exige que estejam certos.

Calendário de referência — agosto/setembro de 2026:
    17/08 seg · 18/08 ter · 19/08 qua · 20/08 qui · 21/08 sex · 22-23/08 fim de semana
    07/09 seg = feriado da Independência
"""

from datetime import date

import pytest

from src.utils.dias_uteis import (
    contar_dias_uteis,
    eh_dia_util,
    listar_dias_uteis,
    proximo_dia_util,
    somar_dias_uteis,
)

FERIADO_INDEPENDENCIA = date(2026, 9, 7)
SEM_FERIADOS: list = []


class TestEhDiaUtil:
    def test_segunda_a_sexta_sem_feriado_e_util(self):
        for dia in range(17, 22):  # 17 a 21 de agosto, seg a sex
            assert eh_dia_util(date(2026, 8, dia), SEM_FERIADOS)

    def test_sabado_e_domingo_nunca_sao_uteis(self):
        assert not eh_dia_util(date(2026, 8, 22), SEM_FERIADOS)  # sábado
        assert not eh_dia_util(date(2026, 8, 23), SEM_FERIADOS)  # domingo

    def test_feriado_em_dia_de_semana_nao_e_util(self):
        assert not eh_dia_util(FERIADO_INDEPENDENCIA, [FERIADO_INDEPENDENCIA])

    def test_feriado_que_cai_no_fim_de_semana_continua_nao_util(self):
        sabado = date(2026, 8, 22)
        assert not eh_dia_util(sabado, [sabado])


class TestContarDiasUteis:
    def test_semana_cheia_sem_feriado_da_5(self):
        assert contar_dias_uteis(date(2026, 8, 17), date(2026, 8, 21), SEM_FERIADOS) == 5

    def test_intervalo_que_atravessa_o_fim_de_semana_ignora_sabado_e_domingo(self):
        # 17/08 (seg) a 28/08 (sex) = 2 semanas cheias
        assert contar_dias_uteis(date(2026, 8, 17), date(2026, 8, 28), SEM_FERIADOS) == 10

    def test_feriado_no_meio_desconta_um_dia(self):
        # semana de 07/09 a 11/09 com a Independência na segunda
        assert contar_dias_uteis(
            date(2026, 9, 7), date(2026, 9, 11), [FERIADO_INDEPENDENCIA]
        ) == 4

    def test_feriado_na_ponta_inicial_desconta(self):
        assert contar_dias_uteis(
            FERIADO_INDEPENDENCIA, FERIADO_INDEPENDENCIA, [FERIADO_INDEPENDENCIA]
        ) == 0

    def test_um_unico_dia_util_conta_1(self):
        assert contar_dias_uteis(date(2026, 8, 17), date(2026, 8, 17), SEM_FERIADOS) == 1

    def test_intervalo_invertido_devolve_zero(self):
        assert contar_dias_uteis(date(2026, 8, 21), date(2026, 8, 17), SEM_FERIADOS) == 0

    def test_data_ausente_devolve_zero(self):
        # escopo sem data_inicio: a contagem ainda não corre
        assert contar_dias_uteis(None, date(2026, 8, 21), SEM_FERIADOS) == 0
        assert contar_dias_uteis(date(2026, 8, 17), None, SEM_FERIADOS) == 0

    def test_semana_de_provas_inteira_zera_a_contagem(self):
        semana_de_provas = [date(2026, 9, 28) for _ in range(1)] + [
            date(2026, 9, d) for d in (29, 30)
        ] + [date(2026, 10, d) for d in (1, 2)]
        assert contar_dias_uteis(date(2026, 9, 28), date(2026, 10, 2), semana_de_provas) == 0


class TestListarDiasUteis:
    def test_devolve_as_datas_e_nao_so_a_contagem(self):
        dias = listar_dias_uteis(date(2026, 8, 17), date(2026, 8, 23), SEM_FERIADOS)
        assert dias == [date(2026, 8, d) for d in range(17, 22)]

    def test_pula_o_feriado_mantendo_a_ordem(self):
        dias = listar_dias_uteis(date(2026, 9, 4), date(2026, 9, 9), [FERIADO_INDEPENDENCIA])
        assert dias == [date(2026, 9, 4), date(2026, 9, 8), date(2026, 9, 9)]


class TestSomarDiasUteis:
    def test_ambientacao_de_5_dias_a_partir_de_uma_segunda(self):
        # kickoff 10/08/2026 (seg) + 5 dias úteis → fecha na sexta 14/08
        assert somar_dias_uteis(date(2026, 8, 10), 5, SEM_FERIADOS) == date(2026, 8, 14)

    def test_conta_o_proprio_dia_de_inicio_como_o_primeiro(self):
        assert somar_dias_uteis(date(2026, 8, 17), 1, SEM_FERIADOS) == date(2026, 8, 17)

    def test_atravessa_o_fim_de_semana(self):
        # sexta 21/08 + 2 dias úteis → segunda 24/08
        assert somar_dias_uteis(date(2026, 8, 21), 2, SEM_FERIADOS) == date(2026, 8, 24)

    def test_pula_o_feriado(self):
        # sexta 04/09 + 2 dias úteis; 07/09 é feriado → cai na terça 08/09
        assert somar_dias_uteis(date(2026, 9, 4), 2, [FERIADO_INDEPENDENCIA]) == date(2026, 9, 8)

    def test_comeca_no_sabado_e_pula_para_segunda(self):
        assert somar_dias_uteis(date(2026, 8, 22), 1, SEM_FERIADOS) == date(2026, 8, 24)

    def test_quantidade_zero_ou_negativa_devolve_a_propria_data(self):
        assert somar_dias_uteis(date(2026, 8, 17), 0, SEM_FERIADOS) == date(2026, 8, 17)
        assert somar_dias_uteis(date(2026, 8, 17), -3, SEM_FERIADOS) == date(2026, 8, 17)

    def test_calendario_impossivel_levanta_erro_em_vez_de_travar(self):
        todos_os_dias = [date(2026, 8, 17) + __import__("datetime").timedelta(days=n) for n in range(365 * 6)]
        with pytest.raises(ValueError, match="dias úteis"):
            somar_dias_uteis(date(2026, 8, 17), 1, todos_os_dias)


class TestProximoDiaUtil:
    def test_dia_util_devolve_ele_mesmo(self):
        assert proximo_dia_util(date(2026, 8, 17), SEM_FERIADOS) == date(2026, 8, 17)

    def test_sabado_devolve_a_segunda(self):
        assert proximo_dia_util(date(2026, 8, 22), SEM_FERIADOS) == date(2026, 8, 24)

    def test_feriado_na_segunda_devolve_a_terca(self):
        assert proximo_dia_util(FERIADO_INDEPENDENCIA, [FERIADO_INDEPENDENCIA]) == date(2026, 9, 8)


class TestAceitaModelsAlemDeDate:
    """O repository devolve models com atributo `.data`; as funções aceitam os dois."""

    def test_objeto_com_atributo_data_e_tratado_como_feriado(self):
        class DiaNaoLetivoFake:
            def __init__(self, data):
                self.data = data

        assert not eh_dia_util(
            FERIADO_INDEPENDENCIA, [DiaNaoLetivoFake(FERIADO_INDEPENDENCIA)]
        )
        assert contar_dias_uteis(
            date(2026, 9, 7), date(2026, 9, 11), [DiaNaoLetivoFake(FERIADO_INDEPENDENCIA)]
        ) == 4
