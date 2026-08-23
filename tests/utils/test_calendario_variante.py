"""A escolha entre os calendários de curso de uma frente.

O teste que mais importa aqui não é nenhum caso novo: é
`TestNadaMudaSemVariante`. Enquanto ninguém marcar um projeto, a plataforma
inteira tem de enxergar exatamente as mesmas datas de antes desta coluna
existir — janela de escopo, atraso, ambientação, cinza do cronograma.
"""

from datetime import date
from types import SimpleNamespace

from src.utils.calendario_variante import (
    apenas_globais,
    escolha_por_frente,
    filtrar_variante,
)

BUSINESS = SimpleNamespace(id=1, calendario_padrao=None)
TECH = SimpleNamespace(id=2, calendario_padrao="Engenharias")
FRENTES = [BUSINESS, TECH]

SETE_DE_SETEMBRO = date(2026, 9, 7)
PROVA_ENG = date(2026, 9, 24)
PROVA_CC = date(2026, 10, 15)
PROVA_BUSINESS = date(2026, 9, 30)


def dia(data, frente_id=None, variante=None):
    return SimpleNamespace(data=data, frente_id=frente_id, variante=variante)


FERIADO = dia(SETE_DE_SETEMBRO)
ENG = dia(PROVA_ENG, frente_id=2, variante="Engenharias")
CC = dia(PROVA_CC, frente_id=2, variante="Ciência da Computação")
BIZ = dia(PROVA_BUSINESS, frente_id=1)
CALENDARIO = [FERIADO, ENG, CC, BIZ]


class TestNadaMudaSemVariante:
    """A invariante: projeto que não escolheu vê o de sempre."""

    def test_projeto_sem_escolha_pega_o_padrao_da_frente(self):
        resultado = filtrar_variante(CALENDARIO, escolha_por_frente(FRENTES))
        assert resultado == [FERIADO, ENG, BIZ]

    def test_o_dia_de_outro_curso_fica_de_fora(self):
        resultado = filtrar_variante(CALENDARIO, escolha_por_frente(FRENTES))
        assert CC not in resultado

    def test_frente_com_um_calendario_so_atravessa_inteira(self):
        """Business não tem variante nenhuma, então nada dela pode sumir."""
        resultado = filtrar_variante(CALENDARIO, escolha_por_frente(FRENTES))
        assert BIZ in resultado

    def test_calendario_sem_variante_alguma_passa_intacto(self):
        """O estado do banco antes da migration: nenhuma linha com variante."""
        antigo = [FERIADO, BIZ, dia(PROVA_ENG, frente_id=2)]
        assert filtrar_variante(antigo, escolha_por_frente(FRENTES)) == antigo


class TestProjetoQueEscolheu:
    def test_projeto_de_cc_troca_engenharias_por_cc(self):
        escolhidos = escolha_por_frente(FRENTES, "Ciência da Computação")
        resultado = filtrar_variante(CALENDARIO, escolhidos)
        assert CC in resultado
        assert ENG not in resultado

    def test_o_feriado_nacional_nunca_sai(self):
        """Sem frente não há curso: 7 de setembro vale para todo mundo."""
        for calendario in (None, "Engenharias", "Ciência da Computação"):
            escolhidos = escolha_por_frente(FRENTES, calendario)
            assert FERIADO in filtrar_variante(CALENDARIO, escolhidos)

    def test_a_escolha_nao_vaza_para_a_outra_frente(self):
        """Projeto sinérgico: escolher CC não pode esvaziar Business.

        A escolha vale para todas as frentes, mas só encontra dia em quem tem
        aquele calendário — em Business ela não casa com nada e o calendário
        da frente inteira continua valendo.
        """
        escolhidos = escolha_por_frente(FRENTES, "Ciência da Computação")
        assert BIZ in filtrar_variante(CALENDARIO, escolhidos)

    def test_escolha_que_nao_existe_em_frente_nenhuma_nao_apaga_nada(self):
        """Um rótulo órfão não pode zerar o calendário de quem tem variante.

        Some com Engenharias, porque a escolha do projeto substitui o padrão —
        é o preço de o rótulo ser a chave, e por isso `UpdateCalendarioUseCase`
        recusa nome que não exista.
        """
        escolhidos = escolha_por_frente(FRENTES, "Medicina")
        resultado = filtrar_variante(CALENDARIO, escolhidos)
        assert FERIADO in resultado and BIZ in resultado


class TestContratoFrouxo:
    """Aceita o que `dias_uteis.normalizar` aceita — a base testa com fakes."""

    def test_objeto_sem_os_campos_novos_atravessa(self):
        antigo = SimpleNamespace(data=SETE_DE_SETEMBRO)
        assert filtrar_variante([antigo], escolha_por_frente(FRENTES)) == [antigo]

    def test_date_puro_atravessa(self):
        assert filtrar_variante([SETE_DE_SETEMBRO], {}) == [SETE_DE_SETEMBRO]

    def test_frente_sem_calendario_padrao_nao_estoura(self):
        sem_campo = SimpleNamespace(id=3)
        assert escolha_por_frente([sem_campo]) == {3: None}


class TestApenasGlobais:
    def test_corta_tudo_que_tem_frente(self):
        assert apenas_globais(CALENDARIO) == [FERIADO]

    def test_a_variante_nao_muda_o_recorte_global(self):
        """Variante só existe dentro de frente, então o global nunca a vê."""
        assert CC not in apenas_globais(CALENDARIO)
