"""Tarefa vencida e a janela seg–dom da semana."""

from datetime import date

from src.utils.tarefa_status import (
    calcular_urgencia,
    dias_para_prazo,
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


# As colunas do kanban são configuráveis pela diretoria, então o que decide
# "encerrada" é a flag da COLUNA — não uma lista de status no código.
COLUNA_ABERTA = False
COLUNA_ENCERRA = True


class TestTarefaVencida:
    def test_prazo_passado_em_coluna_aberta_esta_vencida(self):
        assert eh_vencida(date(2026, 9, 10), COLUNA_ABERTA, QUA_16_09)

    def test_prazo_futuro_nao_esta_vencida(self):
        assert not eh_vencida(date(2026, 9, 20), COLUNA_ABERTA, QUA_16_09)

    def test_prazo_hoje_ainda_nao_venceu(self):
        """Vence no dia SEGUINTE ao prazo — o dia do prazo é para entregar."""
        assert not eh_vencida(QUA_16_09, COLUNA_ABERTA, QUA_16_09)

    def test_coluna_que_encerra_nunca_deixa_vencida(self):
        """Vale para Concluído, Cancelado e qualquer coluna que a diretoria
        criar marcando "encerra a tarefa" — Arquivado, por exemplo."""
        assert not eh_vencida(date(2026, 9, 1), COLUNA_ENCERRA, QUA_16_09)

    def test_coluna_intermediaria_com_prazo_passado_esta_vencida(self):
        """Validação (e qualquer coluna nova que não encerre) ainda conta:
        a tarefa não saiu."""
        assert eh_vencida(date(2026, 9, 1), COLUNA_ABERTA, QUA_16_09)

    def test_sem_prazo_nao_vence(self):
        assert not eh_vencida(None, COLUNA_ABERTA, QUA_16_09)


class TestUrgencia:
    """⏰ A gradação que a tela usa. `vencida` (booleano) continua servindo o
    monitoramento; isto é para o card avisar ANTES de estourar."""

    def test_prazo_passado_e_vencida(self):
        assert calcular_urgencia(date(2026, 9, 10), COLUNA_ABERTA, QUA_16_09) == "vencida"

    def test_vence_hoje_e_critica(self):
        assert calcular_urgencia(QUA_16_09, COLUNA_ABERTA, QUA_16_09) == "critica"

    def test_vence_amanha_e_critica(self):
        assert calcular_urgencia(date(2026, 9, 17), COLUNA_ABERTA, QUA_16_09) == "critica"

    def test_vence_em_tres_dias_e_atencao(self):
        assert calcular_urgencia(date(2026, 9, 19), COLUNA_ABERTA, QUA_16_09) == "atencao"

    def test_vence_em_quatro_dias_e_normal(self):
        assert calcular_urgencia(date(2026, 9, 20), COLUNA_ABERTA, QUA_16_09) == "normal"

    def test_coluna_que_encerra_zera_a_urgencia(self):
        """A tarefa saiu: o prazo não importa mais, nem se já passou."""
        assert calcular_urgencia(date(2026, 1, 1), COLUNA_ENCERRA, QUA_16_09) == "normal"

    def test_urgencia_e_vencida_nunca_discordam(self):
        for prazo in [date(2026, 9, 1), QUA_16_09, date(2026, 9, 30)]:
            for encerra in (COLUNA_ABERTA, COLUNA_ENCERRA):
                venceu = eh_vencida(prazo, encerra, QUA_16_09)
                urgencia = calcular_urgencia(prazo, encerra, QUA_16_09)
                assert venceu == (urgencia == "vencida")


class TestDiasParaPrazo:
    def test_conta_dias_corridos(self):
        assert dias_para_prazo(date(2026, 9, 20), QUA_16_09) == 4

    def test_negativo_quando_ja_passou(self):
        assert dias_para_prazo(date(2026, 9, 10), QUA_16_09) == -6

    def test_zero_no_dia_do_prazo(self):
        assert dias_para_prazo(QUA_16_09, QUA_16_09) == 0


class TestStatusAtivo:
    def test_coluna_que_encerra_nao_conta_como_trabalho_ativo(self):
        assert not esta_ativa(COLUNA_ENCERRA)

    def test_coluna_aberta_conta(self):
        assert esta_ativa(COLUNA_ABERTA)


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
