"""A regra crítica do §5.4 — a fatia com mais chance de sair errada.

O calendário usado é o real do seed (semestre 2026.2): feriado de 07/09 e a
semana de provas de 28/09 a 02/10. Os números abaixo foram conferidos contra
`contar_dias_uteis`, e vários testes trazem a asserção-irmã com o calendário
vazio, para provar que é o feriado que faz a diferença — não o acaso.
"""

from datetime import date, datetime

from src.utils.contagem_dias import (
    calcular_contagem_escopo,
    calcular_contagem_projeto,
    derivar_janelas_pausa,
)

# O calendário 2026.2 do seed.
FERIADOS = [date(2026, 9, 7), date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 15)]
PROVAS = [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2)]
CALENDARIO = FERIADOS + PROVAS

SEG_17_08 = date(2026, 8, 17)
SEX_21_08 = date(2026, 8, 21)
SEG_24_08 = date(2026, 8, 24)
SEX_28_08 = date(2026, 8, 28)
SEG_31_08 = date(2026, 8, 31)
TER_01_09 = date(2026, 9, 1)
SEX_04_09 = date(2026, 9, 4)
DOM_06_09 = date(2026, 9, 6)
SEG_07_09 = date(2026, 9, 7)  # feriado da Independência
SEX_11_09 = date(2026, 9, 11)
SEG_21_09 = date(2026, 9, 21)
SEX_25_09 = date(2026, 9, 25)
SEX_09_10 = date(2026, 10, 9)


class _LinhaHistorico:
    """Dublê de `ProjetoStatusHistoricoModel` — só os 3 campos que importam."""

    def __init__(self, status_anterior, status_novo, alterado_em):
        self.status_anterior = status_anterior
        self.status_novo = status_novo
        self.alterado_em = alterado_em


def _pausou_em(dia: date) -> _LinhaHistorico:
    return _LinhaHistorico("em_andamento", "pausado", datetime.combine(dia, datetime.min.time()))


def _retomou_em(dia: date) -> _LinhaHistorico:
    return _LinhaHistorico("pausado", "em_andamento", datetime.combine(dia, datetime.min.time()))


class TestContagemBasica:
    def test_corrida_normal_uma_semana(self):
        """17/08 (seg) a 21/08 (sex), sem feriado: 5 dias."""
        c = calcular_contagem_escopo(
            data_inicio=SEG_17_08,
            data_entrega_real=None,
            dias_uteis_vendidos=15,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_21_08,
        )
        assert c.consumidos == 5
        assert c.restantes == 10
        assert c.em_contagem is True
        assert c.estourou is False

    def test_feriado_no_meio_custa_exatamente_um_dia(self):
        """17/08 a 11/09 atravessa o feriado de 07/09."""
        com = calcular_contagem_escopo(
            data_inicio=SEG_17_08,
            data_entrega_real=None,
            dias_uteis_vendidos=15,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_11_09,
        )
        sem = calcular_contagem_escopo(
            data_inicio=SEG_17_08,
            data_entrega_real=None,
            dias_uteis_vendidos=15,
            dias_nao_letivos=[],
            referencia=SEX_11_09,
        )
        assert com.consumidos == 19
        assert sem.consumidos == 20

    def test_semana_de_provas_inteira_some(self):
        """21/09 a 09/10: a semana de provas (28/09–02/10) tira 5 dias."""
        com = calcular_contagem_escopo(
            data_inicio=SEG_21_09,
            data_entrega_real=None,
            dias_uteis_vendidos=20,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_09_10,
        )
        sem = calcular_contagem_escopo(
            data_inicio=SEG_21_09,
            data_entrega_real=None,
            dias_uteis_vendidos=20,
            dias_nao_letivos=[],
            referencia=SEX_09_10,
        )
        assert com.consumidos == 10
        assert sem.consumidos == 15

    def test_sem_data_inicio_nao_conta_nada(self):
        """⭐ 'A contagem só corre com data_inicio preenchida' (§5.4), literal."""
        c = calcular_contagem_escopo(
            data_inicio=None,
            data_entrega_real=None,
            dias_uteis_vendidos=20,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_09_10,
        )
        assert c.consumidos == 0
        assert c.restantes == 20
        assert c.em_contagem is False

    def test_estouro_deixa_restantes_negativo(self):
        """Restantes negativo é informação (o 'estourou em N dias'), não bug."""
        c = calcular_contagem_escopo(
            data_inicio=SEG_17_08,
            data_entrega_real=None,
            dias_uteis_vendidos=15,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_11_09,
        )
        assert c.consumidos == 19
        assert c.restantes == -4
        assert c.estourou is True


class TestEntregaCongela:
    def test_escopo_entregue_para_de_contar(self):
        """⭐ §5.4: quando um escopo é entregue, a contagem PAUSA.

        O mesmo escopo, olhado em três momentos diferentes depois da entrega,
        tem que devolver sempre o mesmo número.
        """
        def contar(referencia):
            return calcular_contagem_escopo(
                data_inicio=SEG_17_08,
                data_entrega_real=SEX_04_09,
                dias_uteis_vendidos=15,
                dias_nao_letivos=CALENDARIO,
                referencia=referencia,
            )

        assert contar(SEX_04_09).consumidos == 15
        assert contar(SEX_25_09).consumidos == 15
        assert contar(date(2026, 12, 31)).consumidos == 15

    def test_escopo_entregue_nao_esta_mais_em_contagem(self):
        c = calcular_contagem_escopo(
            data_inicio=SEG_17_08,
            data_entrega_real=SEX_04_09,
            dias_uteis_vendidos=15,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_25_09,
        )
        assert c.em_contagem is False


class TestJanelasDePausa:
    def test_historico_sem_pausa_nao_gera_janela(self):
        historico = [_LinhaHistorico(None, "vendido", datetime(2026, 8, 1))]
        assert derivar_janelas_pausa(historico, SEX_11_09) == []

    def test_pausa_fechada_gera_uma_janela_semiaberta(self):
        historico = [_pausou_em(SEG_24_08), _retomou_em(SEG_31_08)]
        assert derivar_janelas_pausa(historico, SEX_11_09) == [(SEG_24_08, SEG_31_08)]

    def test_pausa_aberta_fecha_um_dia_depois_da_referencia(self):
        """⭐ referencia + 1, não referencia — senão o dia de hoje escaparia da
        pausa e o contador continuaria andando com o projeto parado."""
        historico = [_pausou_em(SEG_07_09)]
        assert derivar_janelas_pausa(historico, SEX_11_09) == [(SEG_07_09, date(2026, 9, 12))]

    def test_duas_pausas_geram_duas_janelas_disjuntas(self):
        historico = [
            _pausou_em(SEG_24_08),
            _retomou_em(SEG_31_08),
            _pausou_em(SEG_07_09),
            _retomou_em(SEX_11_09),
        ]
        assert derivar_janelas_pausa(historico, SEX_25_09) == [
            (SEG_24_08, SEG_31_08),
            (SEG_07_09, SEX_11_09),
        ]

    def test_dois_pausados_seguidos_nao_abrem_duas_janelas(self):
        """Dado inconsistente (não deveria acontecer) não vira janela dupla."""
        historico = [_pausou_em(SEG_24_08), _pausou_em(SEX_28_08), _retomou_em(SEG_31_08)]
        assert derivar_janelas_pausa(historico, SEX_11_09) == [(SEG_24_08, SEG_31_08)]


class TestPausaDescontaDaContagem:
    def test_janela_de_pausa_fechada_desconta_os_dias(self):
        """Pausa [24/08, 31/08) = 24 a 30/08 = 5 dias úteis. 19 - 5 = 14."""
        c = calcular_contagem_escopo(
            data_inicio=SEG_17_08,
            data_entrega_real=None,
            dias_uteis_vendidos=15,
            dias_nao_letivos=CALENDARIO,
            janelas_pausa=[(SEG_24_08, SEG_31_08)],
            referencia=SEX_11_09,
        )
        assert c.consumidos == 14

    def test_pausado_agora_congela_no_numero_do_instante_da_pausa(self):
        """⭐ O teste que pega o off-by-one da convenção semiaberta.

        Pausou em 07/09 e não retomou. Olhando em 11/09, o consumido tem que
        ser exatamente o que estava congelado em 06/09 — nem um dia a mais.
        """
        janelas = derivar_janelas_pausa([_pausou_em(SEG_07_09)], SEX_11_09)
        c = calcular_contagem_escopo(
            data_inicio=SEG_17_08,
            data_entrega_real=None,
            dias_uteis_vendidos=20,
            dias_nao_letivos=CALENDARIO,
            janelas_pausa=janelas,
            referencia=SEX_11_09,
        )
        congelado = calcular_contagem_escopo(
            data_inicio=SEG_17_08,
            data_entrega_real=None,
            dias_uteis_vendidos=20,
            dias_nao_letivos=CALENDARIO,
            referencia=DOM_06_09,
        )
        assert c.consumidos == 15
        assert c.consumidos == congelado.consumidos

    def test_pausa_anterior_ao_inicio_do_escopo_nao_desconta(self):
        """⭐ A interseção. Uma pausa ocorrida durante a ambientação, antes deste
        escopo começar, não pode roubar dias dele."""
        com_pausa = calcular_contagem_escopo(
            data_inicio=TER_01_09,
            data_entrega_real=None,
            dias_uteis_vendidos=15,
            dias_nao_letivos=CALENDARIO,
            janelas_pausa=[(SEG_24_08, SEG_31_08)],
            referencia=SEX_11_09,
        )
        sem_pausa = calcular_contagem_escopo(
            data_inicio=TER_01_09,
            data_entrega_real=None,
            dias_uteis_vendidos=15,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_11_09,
        )
        assert com_pausa.consumidos == 8
        assert com_pausa.consumidos == sem_pausa.consumidos


class TestEscoposEmParaleloEEmSequencia:
    def test_dois_escopos_contam_ao_mesmo_tempo(self):
        """⭐ §5.4: escopos com data_inicio e sem entrega contam EM PARALELO."""
        a = calcular_contagem_escopo(
            data_inicio=SEG_17_08,
            data_entrega_real=None,
            dias_uteis_vendidos=15,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_28_08,
        )
        b = calcular_contagem_escopo(
            data_inicio=SEG_24_08,
            data_entrega_real=None,
            dias_uteis_vendidos=20,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_28_08,
        )
        assert (a.consumidos, a.restantes) == (10, 5)
        assert (b.consumidos, b.restantes) == (5, 15)
        assert a.em_contagem and b.em_contagem

    def test_pausa_entre_escopos_nao_e_contabilizada_por_ninguem(self):
        """⭐ §5.4: 'o período de ajustes entre escopos não é contabilizado'.

        A entregou em 04/09 (congelado); B ainda não começou (sem data_inicio).
        O vão de 05/09 a 25/09 não aparece em contagem nenhuma.
        """
        a = calcular_contagem_escopo(
            data_inicio=SEG_17_08,
            data_entrega_real=SEX_04_09,
            dias_uteis_vendidos=15,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_25_09,
        )
        b = calcular_contagem_escopo(
            data_inicio=None,
            data_entrega_real=None,
            dias_uteis_vendidos=20,
            dias_nao_letivos=CALENDARIO,
            referencia=SEX_25_09,
        )
        assert a.consumidos == 15 and a.em_contagem is False
        assert b.consumidos == 0 and b.em_contagem is False


class _EscopoFalso:
    def __init__(self, id, data_inicio, data_entrega_real, dias, ajustados=0):
        self.id = id
        self.data_inicio = data_inicio
        self.data_entrega_real = data_entrega_real
        self.dias_uteis_vendidos = dias
        self.dias_uteis_ajustados = ajustados


class TestContagemProjetoInteiro:
    def test_deriva_as_janelas_uma_vez_e_aplica_a_todos_os_escopos(self):
        escopos = [
            _EscopoFalso(1, SEG_17_08, None, 15),
            _EscopoFalso(2, SEG_24_08, None, 20),
            _EscopoFalso(3, None, None, 10),
        ]
        historico = [_pausou_em(SEG_24_08), _retomou_em(SEG_31_08)]
        resultado = calcular_contagem_projeto(
            escopos, historico, CALENDARIO, referencia=SEX_11_09
        )

        assert set(resultado) == {1, 2, 3}
        # 19 bruto - 5 de pausa
        assert resultado[1].consumidos == 14
        # 24/08 a 11/09 = 14 bruto, menos a pausa inteira (5) = 9
        assert resultado[2].consumidos == 9
        assert resultado[3].consumidos == 0


class TestBancaCongelaAContagem:
    """⭐ A contagem para na BANCA REALIZADA, não na entrega.

    É o §11 aplicado ao consumo: depois da banca, tudo que se mexe naquele
    escopo é CORREÇÃO, e correção "não consome dias e não é atraso". Contar o
    tempo de arrumar o que a banca apontou como se fosse trabalho vendido
    inflava o estouro — e ele crescia sozinho, um dia por dia, enquanto a
    entrega não fosse registrada.

    ⚠ O sintoma que trouxe isto à tona: a mesma linha da tela mostrava
    "22/12 (+10)" ao lado de "Atraso: 1 dia". Os dois números mediam o mesmo
    estouro com réguas diferentes — o consumo corria até hoje, o atraso parava
    na banca. Os testes abaixo cobrem justamente a igualdade entre eles.
    """

    #: 12 dias úteis vendidos a partir de 14/07 fecham a janela em 29/07.
    INICIO = date(2026, 7, 14)
    BANCA = datetime(2026, 7, 30, 11, 30)  # 1 dia útil além da janela
    HOJE = date(2026, 8, 12)  # duas semanas depois, sem entrega registrada

    def contagem(self, **kwargs):
        base = dict(
            data_inicio=self.INICIO,
            data_entrega_real=None,
            dias_uteis_vendidos=12,
            dias_nao_letivos=[],
            referencia=self.HOJE,
            banca_realizado_em=self.BANCA,
        )
        base.update(kwargs)
        return calcular_contagem_escopo(**base)

    def test_o_consumo_para_na_banca(self):
        """Sem a regra, seriam 22 — os dias de correção entrando como consumo."""
        assert self.contagem().consumidos == 13

    def test_o_estouro_bate_com_o_atraso(self):
        """⭐ A asserção que a tela representa: `(+N)` e "Atraso: N dias" são o
        MESMO número. Enquanto divergirem, a linha se contradiz."""
        c = self.contagem()

        assert -c.restantes == c.atraso == 1

    def test_o_numero_nao_cresce_sozinho_depois_da_banca(self):
        """Duas semanas a mais no relógio não mudam nada: ninguém trabalhou
        mais no vendido, e o que se fez ali é correção."""
        depois = self.contagem(referencia=date(2026, 8, 26))

        assert depois.consumidos == self.contagem().consumidos
        assert depois.atraso == self.contagem().atraso

    def test_em_contagem_acompanha_o_congelamento(self):
        """O campo dizia "ainda correndo" sobre um número já parado."""
        assert self.contagem().em_contagem is False

    def test_sem_banca_realizada_o_relogio_continua(self):
        """A regra é sobre a banca ACONTECER — banca marcada e não realizada
        não congela nada, senão o escopo pararia de consumir sem ter
        apresentado."""
        c = self.contagem(banca_realizado_em=None)

        assert c.consumidos == 22
        assert c.em_contagem is True

    def test_a_entrega_ainda_congela_quando_nao_ha_banca(self):
        """O caminho antigo continua valendo para escopo legado, sem registro
        de banca realizada — `marco_das_correcoes` cai na entrega."""
        c = self.contagem(banca_realizado_em=None, data_entrega_real=date(2026, 7, 30))

        assert c.consumidos == 13
        assert c.em_contagem is False
