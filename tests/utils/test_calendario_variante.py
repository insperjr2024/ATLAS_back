"""O calendário base de um escopo — o par (frente, rótulo).

⭐ O teste que mais importa é `TestOCorteRealmenteCorta`. A versão anterior
deste módulo cortava por VARIANTE e nunca por frente, e o efeito era que a
escolha não escolhia nada: todo projeto contava a união dos dias de todas as
frentes, e um escopo de Business parava na semana de avaliação da Tech. É essa
união que os testes daqui proíbem de voltar.
"""

from datetime import date
from types import SimpleNamespace

from src.utils.calendario_variante import (
    apenas_globais,
    datas_por_escopo,
    do_calendario,
    do_escopo,
    eh_global,
)

SETE_DE_SETEMBRO = date(2026, 9, 7)
PROVA_ENG = date(2026, 9, 24)
PROVA_CC = date(2026, 10, 15)
PROVA_BUSINESS = date(2026, 9, 30)


def dia(data, frente_id=None, variante=None):
    return SimpleNamespace(data=data, frente_id=frente_id, variante=variante)


def escopo(id, frente_id, calendario=None):
    return SimpleNamespace(id=id, frente_id=frente_id, calendario=calendario)


FERIADO = dia(SETE_DE_SETEMBRO)
ENG = dia(PROVA_ENG, frente_id=2, variante="Engenharias")
CC = dia(PROVA_CC, frente_id=2, variante="Ciência da Computação")
BIZ = dia(PROVA_BUSINESS, frente_id=1)
CALENDARIO = [FERIADO, ENG, CC, BIZ]

#: Business tem um calendário só, então o rótulo dele é nulo — o mesmo nulo de
#: `dia_nao_letivo.variante`, e não "não escolhido".
DE_BUSINESS = escopo(10, frente_id=1)
DE_ENGENHARIAS = escopo(20, frente_id=2, calendario="Engenharias")
DE_CC = escopo(30, frente_id=2, calendario="Ciência da Computação")


class TestOCorteRealmenteCorta:
    """⚠ A regressão: o dia de OUTRA FRENTE não entra."""

    def test_escopo_de_business_nao_ve_a_prova_da_tech(self):
        resultado = do_escopo(CALENDARIO, DE_BUSINESS)
        assert ENG not in resultado and CC not in resultado

    def test_escopo_da_tech_nao_ve_a_prova_de_business(self):
        assert BIZ not in do_escopo(CALENDARIO, DE_ENGENHARIAS)

    def test_cada_escopo_ve_o_proprio_dia(self):
        assert BIZ in do_escopo(CALENDARIO, DE_BUSINESS)
        assert ENG in do_escopo(CALENDARIO, DE_ENGENHARIAS)
        assert CC in do_escopo(CALENDARIO, DE_CC)


class TestOCursoDentroDaFrente:
    def test_engenharias_nao_ve_ciencia_da_computacao(self):
        """As duas moram na mesma frente — é o caso que criou a variante."""
        assert CC not in do_escopo(CALENDARIO, DE_ENGENHARIAS)

    def test_ciencia_da_computacao_nao_ve_engenharias(self):
        assert ENG not in do_escopo(CALENDARIO, DE_CC)

    def test_rotulo_nulo_numa_frente_com_variantes_nao_e_curinga(self):
        """Quem não escolheu curso não pode receber a semana de avaliação de um.

        Só entram os dias que valem para a frente INTEIRA (`variante` nula) —
        aqui, nenhum.
        """
        sem_curso = escopo(40, frente_id=2)
        assert do_escopo(CALENDARIO, sem_curso) == [FERIADO]


class TestOFeriadoAtravessaSempre:
    def test_todo_escopo_ve_o_feriado_nacional(self):
        for e in (DE_BUSINESS, DE_ENGENHARIAS, DE_CC):
            assert FERIADO in do_escopo(CALENDARIO, e)

    def test_e_o_unico_que_sobra_num_escopo_de_frente_sem_calendario(self):
        """Processos não teve calendário carregado: sobra o que é do país."""
        de_processos = escopo(50, frente_id=3)
        assert do_escopo(CALENDARIO, de_processos) == [FERIADO]

    def test_eh_global_le_a_frente(self):
        assert eh_global(FERIADO)
        assert not eh_global(ENG)


class TestDatasPorEscopo:
    def test_devolve_as_datas_de_cada_escopo(self):
        resultado = datas_por_escopo(CALENDARIO, [DE_BUSINESS, DE_ENGENHARIAS])

        assert resultado[DE_BUSINESS.id] == [SETE_DE_SETEMBRO, PROVA_BUSINESS]
        assert resultado[DE_ENGENHARIAS.id] == [SETE_DE_SETEMBRO, PROVA_ENG]

    def test_dois_escopos_da_mesma_frente_recebem_o_mesmo_calendario(self):
        outro = escopo(21, frente_id=2, calendario="Engenharias")
        resultado = datas_por_escopo(CALENDARIO, [DE_ENGENHARIAS, outro])

        assert resultado[DE_ENGENHARIAS.id] == resultado[outro.id]

    def test_projeto_sinergico_recebe_calendarios_diferentes(self):
        """⭐ A razão de a base ser do escopo e não do projeto."""
        resultado = datas_por_escopo(CALENDARIO, [DE_BUSINESS, DE_ENGENHARIAS])

        assert resultado[DE_BUSINESS.id] != resultado[DE_ENGENHARIAS.id]

    def test_aceita_gerador(self):
        """`datas_por_escopo` percorre os dias uma vez por escopo — um gerador
        se esgotaria no primeiro."""
        resultado = datas_por_escopo(iter(CALENDARIO), [DE_BUSINESS, DE_ENGENHARIAS])

        assert len(resultado[DE_ENGENHARIAS.id]) == 2


class TestContratoFrouxo:
    """Aceita o que `dias_uteis.normalizar` aceita — a base testa com fakes."""

    def test_objeto_sem_os_campos_novos_conta_como_global(self):
        antigo = SimpleNamespace(data=SETE_DE_SETEMBRO)
        assert do_escopo([antigo], DE_ENGENHARIAS) == [antigo]

    def test_escopo_sem_os_campos_novos_recebe_so_os_globais(self):
        sem_campos = SimpleNamespace(id=99)
        assert do_escopo(CALENDARIO, sem_campos) == [FERIADO]

    def test_do_calendario_aceita_frente_e_rotulo_soltos(self):
        assert do_calendario(CALENDARIO, 2, "Engenharias") == [FERIADO, ENG]


class TestApenasGlobais:
    def test_corta_tudo_que_tem_frente(self):
        assert apenas_globais(CALENDARIO) == [FERIADO]

    def test_a_variante_nao_muda_o_recorte_global(self):
        """Variante só existe dentro de frente, então o global nunca a vê."""
        assert CC not in apenas_globais(CALENDARIO)
