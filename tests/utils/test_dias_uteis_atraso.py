"""Atraso medido em dias ÚTEIS — a régua única do sistema.

Vale para a tarefa vencida da aba de Execução (§7.2) e também para a banca e a
entrega do §7.4, desde que a diretoria confirmou (2026-08-04) que ali não são
dias corridos. Alguns testes comparam com a contagem corrida de propósito, para
deixar o tamanho da diferença explícito.
"""

from datetime import date

from src.utils.dias_uteis import dias_uteis_de_atraso

# Setembro de 2026: dia 11 é sexta, 12 sábado, 13 domingo, 14 segunda.
SEX_11 = date(2026, 9, 11)
SAB_12 = date(2026, 9, 12)
SEG_14 = date(2026, 9, 14)
TER_15 = date(2026, 9, 15)
SEX_18 = date(2026, 9, 18)


class TestDiasUteisDeAtraso:
    def test_prazo_no_futuro_nao_esta_atrasado(self):
        assert dias_uteis_de_atraso(SEX_18, SEG_14, []) == 0

    def test_prazo_hoje_ainda_nao_atrasou(self):
        """O dia do prazo é para entregar — mesma convenção de `eh_vencida`."""
        assert dias_uteis_de_atraso(SEG_14, SEG_14, []) == 0

    def test_um_dia_util_depois_do_prazo(self):
        assert dias_uteis_de_atraso(SEG_14, TER_15, []) == 1

    def test_fim_de_semana_nao_conta_como_atraso(self):
        """O ponto da feature: venceu na sexta, hoje é segunda.

        São 3 dias corridos, mas o time só teve 1 dia de trabalho para
        resolver — cobrar 3 seria cobrar o fim de semana.
        """
        assert dias_uteis_de_atraso(SEX_11, SEG_14, []) == 1
        assert (SEG_14 - SEX_11).days == 3

    def test_atraso_que_termina_no_sabado_conta_so_os_uteis(self):
        assert dias_uteis_de_atraso(SEX_11, SAB_12, []) == 0

    def test_semana_inteira_de_atraso(self):
        assert dias_uteis_de_atraso(SEX_11, SEX_18, []) == 5

    def test_dia_nao_letivo_no_meio_nao_conta(self):
        """Feriado, prova e recesso vêm do calendário do Insper (§5.4)."""
        assert dias_uteis_de_atraso(SEG_14, SEX_18, [TER_15]) == 3

    def test_dia_nao_letivo_aceita_model_com_atributo_data(self):
        class FakeDiaNaoLetivo:
            data = TER_15

        assert dias_uteis_de_atraso(SEG_14, SEX_18, [FakeDiaNaoLetivo()]) == 3

    def test_prazo_nulo_devolve_zero(self):
        assert dias_uteis_de_atraso(None, SEG_14, []) == 0

    def test_referencia_nula_devolve_zero(self):
        assert dias_uteis_de_atraso(SEG_14, None, []) == 0

    def test_todo_o_intervalo_nao_letivo_zera_o_atraso(self):
        """Semana de provas inteira: o prazo venceu, mas não houve dia de
        trabalho para cumpri-lo."""
        semana_de_provas = [date(2026, 9, 15), date(2026, 9, 16), date(2026, 9, 17)]
        assert dias_uteis_de_atraso(SEG_14, date(2026, 9, 17), semana_de_provas) == 0
