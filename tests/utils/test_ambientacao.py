"""A janela de ambientação do §5.3 — kickoff + N dias úteis.

O que estes testes prendem é a BORDA: o dia do fim ainda é ambientação, e a
virada é no dia seguinte. Errar essa borda em um dia significa cortar (ou dar
de graça) um dia útil de ambientação em todo projeto do semestre.
"""

from datetime import date

from src.utils.ambientacao import ambientacao_encerrada, fim_da_ambientacao

# Agosto de 2026: 3 é segunda, 7 sexta, 8 e 9 fim de semana, 10 segunda.
SEG_03 = date(2026, 8, 3)
QUA_05 = date(2026, 8, 5)
SEX_07 = date(2026, 8, 7)
SAB_08 = date(2026, 8, 8)
SEG_10 = date(2026, 8, 10)
TER_11 = date(2026, 8, 11)


class TestFimDaAmbientacao:
    def test_conta_o_kickoff_como_primeiro_dia(self):
        """5 dias úteis a partir de uma segunda fecham na sexta, não na outra
        segunda — o kickoff é o 1º dia, não o dia zero."""
        assert fim_da_ambientacao(SEG_03, 5, []) == SEX_07

    def test_pula_fim_de_semana(self):
        assert fim_da_ambientacao(QUA_05, 5, []) == TER_11

    def test_pula_dia_nao_letivo(self):
        """Feriado na quarta empurra o fim para a segunda seguinte."""
        assert fim_da_ambientacao(SEG_03, 5, [QUA_05]) == SEG_10

    def test_sem_kickoff_nao_ha_janela(self):
        assert fim_da_ambientacao(None, 5, []) is None

    def test_zero_dias_nao_ha_janela(self):
        """Projeto sem ambientação não tem o que encerrar — devolver o próprio
        kickoff faria a virada esperar um dia à toa."""
        assert fim_da_ambientacao(SEG_03, 0, []) is None


class TestAmbientacaoEncerrada:
    def test_o_dia_do_fim_ainda_e_ambientacao(self):
        assert ambientacao_encerrada(SEG_03, 5, [], referencia=SEX_07) is False

    def test_encerra_no_dia_seguinte(self):
        assert ambientacao_encerrada(SEG_03, 5, [], referencia=SAB_08) is True

    def test_antes_do_fim_segue_em_ambientacao(self):
        assert ambientacao_encerrada(SEG_03, 5, [], referencia=QUA_05) is False

    def test_sem_janela_nunca_encerra(self):
        """Sem kickoff ou sem dias, a saída continua sendo pela mão de alguém."""
        assert ambientacao_encerrada(None, 5, [], referencia=TER_11) is False
        assert ambientacao_encerrada(SEG_03, 0, [], referencia=TER_11) is False
