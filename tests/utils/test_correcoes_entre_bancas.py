"""⭐ §11: o que se pinta DEPOIS da banca é correção — inclusive entre duas bancas.

A régua é a **PRIMEIRA** realização, não a tentativa corrente. Estes testes
existem porque a diferença entre as duas produzia números errados na tela, e
não de um jeito discreto: o atraso de dois projetos do seed estava inflado em
12 e 4 dias, cobrando do time exatamente o retrabalho que a banca pediu.

⚠ **Por que `banca.realizado_em` não serve.** Remarcar uma banca reprovada zera
essa coluna (`_campos_da_remarcacao`) — é ela que descreve a tentativa em
curso, e a que vem tem de nascer limpa. Quem lê só ela conclui que a banca
nunca aconteceu:

- o escopo volta a "em contagem" e os dias do retrabalho passam a consumir
  trabalho VENDIDO, um por dia, sem ninguém trabalhar no que foi vendido;
- o atraso cresce junto;
- a coluna Correções zera, e o retrabalho fica sem lugar na tela.

E há o caso silencioso: com as duas tentativas já realizadas, usar a data da 2ª
faz os dias ENTRE elas contarem como trabalho vendido — quando são, por
definição, a correção que a 1ª apontou.
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from src.utils.janela_escopo import dias_de_correcao, marco_das_correcoes, primeira_realizacao

SEM_FERIADO: list = []


def sessao(numero, realizado_em=None, resultado=None, encerrada=False):
    return SimpleNamespace(
        numero=numero,
        realizado_em=realizado_em,
        resultado=resultado,
        encerrada_em=datetime(2026, 8, 1) if encerrada else None,
    )


def etapa(inicio, fim):
    return SimpleNamespace(data_inicio=inicio, data_fim=fim)


class TestPrimeiraRealizacao:
    def test_banca_reprovada_e_remarcada_nao_perde_o_marco(self):
        """⭐ O caso que motivou tudo.

        A linha de `banca` está com `realizado_em=None` (a 2ª ainda não
        aconteceu), mas a 1ª aconteceu em 27/07 — e é dali que o retrabalho
        corre.
        """
        banca = SimpleNamespace(id=1, realizado_em=None, resultado=None)
        sessoes = [
            sessao(1, datetime(2026, 7, 27, 14, 30), "nao_aprovada", encerrada=True),
            sessao(2),  # marcada para o futuro, ainda não aconteceu
        ]

        assert primeira_realizacao(banca, sessoes) == datetime(2026, 7, 27, 14, 30)

    def test_com_as_duas_realizadas_vale_a_primeira(self):
        """⚠ O caso silencioso: usar a 2ª faz o retrabalho ENTRE elas contar
        como trabalho vendido."""
        banca = SimpleNamespace(id=1, realizado_em=datetime(2026, 7, 16, 14, 0))
        sessoes = [
            sessao(1, datetime(2026, 7, 9, 14, 0), "nao_aprovada", encerrada=True),
            sessao(2, datetime(2026, 7, 16, 14, 0), "aprovada", encerrada=True),
        ]

        assert primeira_realizacao(banca, sessoes) == datetime(2026, 7, 9, 14, 0)

    def test_uma_sessao_so_devolve_ela_mesma(self):
        banca = SimpleNamespace(id=1, realizado_em=datetime(2026, 7, 22, 14, 30))
        sessoes = [sessao(1, datetime(2026, 7, 22, 14, 30))]

        assert primeira_realizacao(banca, sessoes) == datetime(2026, 7, 22, 14, 30)

    def test_sem_sessao_cai_na_coluna_da_banca(self):
        """⚠ Banca anterior a `banca_sessao`. Sem este fallback, todo escopo
        legado voltaria a contar dias como se a banca nunca tivesse ocorrido."""
        banca = SimpleNamespace(id=1, realizado_em=datetime(2026, 7, 1, 10, 0))

        assert primeira_realizacao(banca, []) == datetime(2026, 7, 1, 10, 0)

    def test_nenhuma_tentativa_realizada_nao_inventa_marco(self):
        """A banca está marcada mas não aconteceu: tudo ainda é trabalho
        vendido, e o escopo continua em contagem."""
        banca = SimpleNamespace(id=1, realizado_em=None)

        assert primeira_realizacao(banca, [sessao(1), sessao(2)]) is None

    def test_banca_ausente_nao_estoura(self):
        assert primeira_realizacao(None, []) is None


class TestOsDiasSaemDaConta:
    """O efeito que o usuário enxerga: pintar depois da banca não consome dias."""

    def test_dias_entre_a_primeira_banca_e_a_segunda_sao_correcao(self):
        marco = marco_das_correcoes(datetime(2026, 7, 9, 14, 0), None)
        # Retrabalho pintado entre as duas bancas (09/07 → 16/07).
        etapas = [etapa(date(2026, 7, 10), date(2026, 7, 15))]

        assert dias_de_correcao(etapas, marco, SEM_FERIADO) == 4

    def test_dia_da_propria_banca_nao_conta_como_correcao(self):
        """A correção começa no dia SEGUINTE: o dia da banca ainda é o dia da
        banca, não do conserto que ela pediu."""
        marco = marco_das_correcoes(datetime(2026, 7, 9, 14, 0), None)

        assert dias_de_correcao([etapa(date(2026, 7, 9), date(2026, 7, 9))], marco, SEM_FERIADO) == 0

    def test_etapa_que_atravessa_a_banca_conta_so_a_metade_de_depois(self):
        marco = marco_das_correcoes(datetime(2026, 7, 9, 14, 0), None)
        etapas = [etapa(date(2026, 7, 6), date(2026, 7, 14))]

        # 10, 13 e 14 de julho (11 e 12 caem no fim de semana).
        assert dias_de_correcao(etapas, marco, SEM_FERIADO) == 3

    def test_sem_banca_realizada_nada_e_correcao(self):
        """Enquanto a banca não acontece, tudo que se pinta é trabalho
        vendido — é o que mantém a contagem correndo."""
        assert dias_de_correcao([etapa(date(2026, 7, 1), date(2026, 7, 10))], None, SEM_FERIADO) == 0

    def test_dias_distintos_nao_soma_de_etapas(self):
        """Duas etapas no mesmo dia são UM dia de correção."""
        marco = marco_das_correcoes(datetime(2026, 7, 9, 14, 0), None)
        etapas = [etapa(date(2026, 7, 10), date(2026, 7, 10)), etapa(date(2026, 7, 10), date(2026, 7, 10))]

        assert dias_de_correcao(etapas, marco, SEM_FERIADO) == 1


@pytest.mark.parametrize(
    "realizacoes,esperado",
    [
        ([], None),
        ([datetime(2026, 7, 9)], datetime(2026, 7, 9)),
        ([datetime(2026, 7, 16), datetime(2026, 7, 9)], datetime(2026, 7, 9)),
        ([datetime(2026, 7, 9), datetime(2026, 7, 16), datetime(2026, 7, 30)], datetime(2026, 7, 9)),
    ],
)
def test_sempre_a_menor_data(realizacoes, esperado):
    """A ordem das sessões na lista não importa — vale a mais antiga."""
    banca = SimpleNamespace(id=1, realizado_em=None)
    sessoes = [sessao(i + 1, d) for i, d in enumerate(realizacoes)]

    assert primeira_realizacao(banca, sessoes) == esperado
