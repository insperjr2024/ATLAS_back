"""😴 O VÃO ENTRE ESCOPOS: da entrega ao cliente de um até a reunião inicial do
seguinte.

É o intervalo em que os projetos costumam morrer — o escopo anterior fechou, o
próximo não começou, e ninguém percebe porque nenhum prazo está correndo.

⚠ A métrica existia mas não media isso. Três defeitos, todos cobertos abaixo:

1. **Media sempre até HOJE**, mesmo com o próximo escopo já iniciado — então o
   vão que de fato aconteceu nunca aparecia, e o número só existia enquanto
   ninguém resolvia;
2. **Dava número NEGATIVO** quando a entrega estava registrada para o futuro
   (o card exibia "-16 dias parado");
3. **Sumia se qualquer escopo estivesse em curso**, escondendo o vão dos
   projetos que rodam escopos em sequência — os que a métrica vigia.

O use case é chamado direto, com o `ctx` montado à mão: `_tempo_parado` é
função de composição pura sobre ele, então não precisa de banco nenhum.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from src.use_cases.monitoramento.monitoramento import VisaoGeralUseCase

HOJE = date(2026, 8, 12)


def escopo(id, *, inicio=None, entrega=None, status="em_andamento"):
    return SimpleNamespace(
        id=id,
        data_inicio=inicio,
        data_entrega_real=entrega,
        status=status,
    )


def vaos(escopos, *, status_projeto="em_andamento", hoje=HOJE):
    projeto = SimpleNamespace(id=1, nome="Projeto Alfa", status=status_projeto)
    ctx = {
        "escopos_por_projeto": {1: escopos},
        "nomes_escopo": {e.id: f"escopo {e.id}" for e in escopos},
    }
    return VisaoGeralUseCase(db=None)._tempo_parado([projeto], ctx, hoje)


class TestVaoFechado:
    """O próximo escopo já teve reunião inicial: o vão tem tamanho definitivo."""

    def test_mede_da_entrega_ate_a_reuniao_inicial(self):
        """⭐ A regra em uma linha. Antes isto devolvia (hoje - entrega) = 33."""
        (vao,) = vaos(
            [
                escopo(1, inicio=date(2026, 6, 1), entrega=date(2026, 7, 10)),
                escopo(2, inicio=date(2026, 7, 15)),
            ]
        )

        assert vao["dias_parado"] == 5
        assert vao["aberto"] is False
        assert vao["escopo_seguinte"] == "escopo 2"

    def test_aparece_mesmo_com_o_proximo_escopo_em_curso(self):
        """O defeito 3: o vão sumia porque havia escopo rodando. Justamente o
        caso de um projeto sequencial saudável, que é onde a métrica serve."""
        resultado = vaos(
            [
                escopo(1, inicio=date(2026, 6, 1), entrega=date(2026, 7, 10)),
                escopo(2, inicio=date(2026, 7, 15)),
            ]
        )

        assert len(resultado) == 1

    def test_escopos_sobrepostos_nao_sao_vao(self):
        """O seguinte começou ANTES de o anterior entregar: trabalho em
        paralelo, não espera. Sem o corte, viraria um número negativo."""
        assert vaos(
            [
                escopo(1, inicio=date(2026, 6, 1), entrega=date(2026, 7, 10)),
                escopo(2, inicio=date(2026, 7, 1)),
            ]
        ) == []


class TestVaoAberto:
    """Ninguém começou o próximo: o vão corre até hoje. É o alerta."""

    def test_conta_da_entrega_ate_hoje(self):
        (vao,) = vaos(
            [
                escopo(1, inicio=date(2026, 6, 1), entrega=date(2026, 8, 2)),
                escopo(2, status="nao_iniciado"),
            ]
        )

        assert vao["dias_parado"] == 10
        assert vao["aberto"] is True
        assert vao["escopo_seguinte"] is None

    def test_entrega_no_futuro_nao_abre_vao(self):
        """⭐ O defeito 2, que a tela mostrava como "-16 dias parado". Uma
        entrega que ainda não aconteceu não deixou ninguém esperando."""
        assert vaos(
            [
                escopo(1, inicio=date(2026, 6, 1), entrega=date(2026, 8, 28)),
                escopo(2, status="nao_iniciado"),
            ]
        ) == []

    def test_o_ultimo_escopo_entregue_nao_abre_vao(self):
        """Todos já rodaram — não há próximo pelo qual esperar.

        O par 2 → 1 continua sendo um vão fechado (entrega 01/06, reunião
        inicial 10/06); o que NÃO existe é um vão depois do escopo 1, que é o
        último. Sem esse corte, todo projeto concluído ficaria "parado" para
        sempre.
        """
        resultado = vaos(
            [
                escopo(1, inicio=date(2026, 6, 10), entrega=date(2026, 7, 10)),
                escopo(2, inicio=date(2026, 5, 1), entrega=date(2026, 6, 1)),
            ]
        )

        assert [(v["escopo_entregue"], v["dias_parado"]) for v in resultado] == [
            ("escopo 2", 9)
        ]


class TestPassagemDeBastaoPerfeita:
    def test_reuniao_inicial_no_mesmo_dia_da_entrega_nao_e_vao(self):
        """Zero dia parado é o caso BEM-SUCEDIDO — reportá-lo num card de tempo
        parado seria enchê-lo justamente com quem acertou."""
        assert vaos(
            [
                escopo(1, inicio=date(2026, 6, 1), entrega=date(2026, 7, 10)),
                escopo(2, inicio=date(2026, 7, 10)),
            ]
        ) == []


class TestRecorte:
    def test_projeto_de_um_escopo_so_nao_tem_vao(self):
        """A métrica é sobre a SEQUÊNCIA — com um escopo não há entre."""
        assert vaos([escopo(1, inicio=date(2026, 6, 1), entrega=date(2026, 7, 10))]) == []

    def test_escopo_cancelado_sai_da_conta(self):
        """Cancelado não é "próximo a começar": ninguém está esperando por ele."""
        assert vaos(
            [
                escopo(1, inicio=date(2026, 6, 1), entrega=date(2026, 7, 10)),
                escopo(2, status="cancelado"),
            ]
        ) == []

    @pytest.mark.parametrize("status", ["finalizado", "pausado"])
    def test_projeto_finalizado_ou_pausado_fica_de_fora(self, status):
        """Parado de propósito não é parado por esquecimento."""
        assert (
            vaos(
                [
                    escopo(1, inicio=date(2026, 6, 1), entrega=date(2026, 8, 2)),
                    escopo(2, status="nao_iniciado"),
                ],
                status_projeto=status,
            )
            == []
        )


class TestVariosVaos:
    def test_tres_escopos_dao_dois_vaos(self):
        """⭐ Um vão por PAR, não um por projeto: eles podem ser bem
        diferentes, e a média entre eles não descreveria nenhum."""
        resultado = vaos(
            [
                escopo(1, inicio=date(2026, 5, 1), entrega=date(2026, 6, 1)),
                escopo(2, inicio=date(2026, 6, 3), entrega=date(2026, 7, 1)),
                escopo(3, inicio=date(2026, 7, 21)),
            ]
        )

        assert sorted(v["dias_parado"] for v in resultado) == [2, 20]

    def test_o_vao_aberto_vem_antes_do_fechado(self):
        """O aberto é o que ainda dá para resolver; o fechado é histórico."""
        resultado = vaos(
            [
                escopo(1, inicio=date(2026, 5, 1), entrega=date(2026, 6, 1)),
                escopo(2, inicio=date(2026, 6, 3), entrega=date(2026, 8, 5)),
                escopo(3, status="nao_iniciado"),
            ]
        )

        assert [v["aberto"] for v in resultado] == [True, False]


class TestCalendarioDaJanela:
    """⭐ A janela do escopo termina no FUTURO — o calendário tem de alcançá-la.

    O Monitoramento carrega os dias não letivos por intervalo para não puxar a
    tabela inteira. Só que a janela de um escopo em curso fecha depois de hoje,
    e um recorte que para na data de referência **esconde os feriados que ela
    atravessa** — cada feriado escondido encurta a janela em um dia útil.

    O sintoma real (TX1, 2026-08-12): escopo iniciado em 19/08 com 9 vendidos +
    5 ajustados fecha em 08/09 atravessando o feriado de 07/09. Sem o feriado no
    calendário, a janela era calculada até 07/09 e a banca feita em 08/09 — no
    último dia do prazo — aparecia como 1 DIA DE ATRASO, cobrando um coordenador
    que tinha entregado dentro do combinado.
    """

    FERIADO_FUTURO = date(2026, 9, 7)

    def janela_do_tx1(self, dias_nao_letivos):
        from src.utils.janela_escopo import calcular_janela

        return calcular_janela(
            date(2026, 8, 19), 9, 5, dias_nao_letivos, referencia=date(2026, 8, 12)
        )

    def test_o_feriado_futuro_empurra_o_fim_da_janela(self):
        com = self.janela_do_tx1([self.FERIADO_FUTURO])
        sem = self.janela_do_tx1([])

        assert com.fim == date(2026, 9, 8)
        # A prova do defeito: sem o feriado, a janela fecha um dia antes.
        assert sem.fim == date(2026, 9, 7)

    def test_banca_no_ultimo_dia_da_janela_nao_e_atraso(self):
        """⭐ O caso do TX1: a banca caiu no último dia do prazo."""
        from datetime import datetime

        from src.utils.janela_escopo import dias_de_atraso

        banca = datetime(2026, 9, 8, 14, 0)
        calendario = [self.FERIADO_FUTURO]

        assert (
            dias_de_atraso(
                self.janela_do_tx1(calendario),
                banca,
                calendario,
                referencia=date(2026, 8, 12),
            )
            == 0
        )

    def test_o_monitoramento_carrega_o_calendario_inteiro(self):
        """A correção em si: a varredura de janela não usa recorte por
        intervalo. Se alguém trocar por `_dias_nao_letivos(…, hoje)` de novo, o
        feriado futuro some e o TX1 volta a aparecer atrasado."""
        import inspect

        from src.use_cases.monitoramento.monitoramento import (
            AtrasosUseCase,
            VisaoGeralUseCase,
        )

        for metodo in (
            AtrasosUseCase._escopos_atrasados,
            VisaoGeralUseCase._metricas_de_janela,
        ):
            fonte = inspect.getsource(metodo)
            assert "_calendario_de_janela()" in fonte
            assert "nao_letivos = self._dias_nao_letivos(" not in fonte
