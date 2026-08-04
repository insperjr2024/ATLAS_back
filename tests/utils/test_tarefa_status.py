"""Tarefa vencida e a janela seg–dom da semana."""

from datetime import date

from src.utils.tarefa_status import (
    eh_vencida,
    esta_ativa,
    fim_semana,
    inicio_semana,
    janela_semana,
)

# 2026-09-16 é uma quarta-feira.
QUA_16_09 = date(2026, 9, 16)
SEG_14_09 = date(2026, 9, 14)
DOM_20_09 = date(2026, 9, 20)


class TestTarefaVencida:
    def test_prazo_passado_e_status_ativo_esta_vencida(self):
        assert eh_vencida(date(2026, 9, 10), "em_andamento", QUA_16_09)

    def test_prazo_futuro_nao_esta_vencida(self):
        assert not eh_vencida(date(2026, 9, 20), "em_andamento", QUA_16_09)

    def test_prazo_hoje_ainda_nao_venceu(self):
        """Vence no dia SEGUINTE ao prazo — o dia do prazo é para entregar."""
        assert not eh_vencida(QUA_16_09, "a_fazer", QUA_16_09)

    def test_concluida_nunca_esta_vencida(self):
        assert not eh_vencida(date(2026, 9, 1), "concluido", QUA_16_09)

    def test_cancelada_nunca_esta_vencida(self):
        assert not eh_vencida(date(2026, 9, 1), "cancelado", QUA_16_09)

    def test_validacao_com_prazo_passado_esta_vencida(self):
        """Validação não é terminal: a tarefa ainda não saiu."""
        assert eh_vencida(date(2026, 9, 1), "validacao", QUA_16_09)


class TestStatusAtivo:
    def test_terminais_nao_sao_ativos(self):
        assert not esta_ativa("concluido")
        assert not esta_ativa("cancelado")

    def test_os_outros_tres_sao_ativos(self):
        for status in ("a_fazer", "em_andamento", "validacao"):
            assert esta_ativa(status)


class TestJanelaDaSemana:
    def test_semana_vai_de_segunda_a_domingo(self):
        assert inicio_semana(QUA_16_09) == SEG_14_09
        assert fim_semana(QUA_16_09) == DOM_20_09

    def test_segunda_e_o_proprio_inicio(self):
        assert inicio_semana(SEG_14_09) == SEG_14_09

    def test_domingo_ainda_pertence_a_semana_que_comecou_na_segunda(self):
        """O ponto da convenção seg–dom: domingo fecha a semana, não abre."""
        assert inicio_semana(DOM_20_09) == SEG_14_09
        assert fim_semana(DOM_20_09) == DOM_20_09

    def test_janela_devolve_o_par(self):
        assert janela_semana(QUA_16_09) == (SEG_14_09, DOM_20_09)

    def test_semana_seguinte_nao_se_sobrepoe(self):
        assert inicio_semana(date(2026, 9, 21)) == date(2026, 9, 21)
