"""Os dois percentuais da Visão geral, e por que eles não fecham 100 juntos.

`placar_gestao` conta só **banca** atrasada — o §7.1 tira a entrega ao cliente
de propósito, porque depende da agenda dele. `atrasados_gestao` conta
**qualquer** motivo. Os dois aparecem lado a lado na tela, e alguém vai somar.

Medido no banco de demonstração: placar 47,4% e atrasados 68,4%. `100 - 47,4`
daria 52,6%, que não é nenhum dos dois. A diferença são os projetos atrasados
só por entrega.
"""

import pytest


def placar(no_prazo: int, em_curso: int) -> float:
    """% sem banca atrasada. Sem projeto em curso, 100 — nada a cobrar."""
    return round(no_prazo / em_curso * 100, 1) if em_curso else 100.0


def percentual_atrasados(atrasados: int, em_curso: int) -> float:
    """% com algum atraso. Sem projeto em curso, 0 — não 100."""
    return round(atrasados / em_curso * 100, 1) if em_curso else 0.0


class TestBaseVazia:
    """Sem projeto em curso, os dois dividiriam por zero.

    Os neutros são OPOSTOS de propósito: 100% no placar significa "nada a
    cobrar"; 0% em atrasados significa "nenhum atraso". Igualar os dois faria
    um deles mentir.
    """

    def test_placar_sem_projeto_e_cem(self):
        assert placar(0, 0) == 100.0

    def test_atrasados_sem_projeto_e_zero(self):
        assert percentual_atrasados(0, 0) == 0.0


class TestOsDoisNaoSaoComplementares:
    def test_o_caso_real_do_banco_de_demonstracao(self):
        """19 em curso: 9 sem banca atrasada, 13 com algum atraso."""
        assert placar(9, 19) == 47.4
        assert percentual_atrasados(13, 19) == 68.4
        # A soma passa de 100 — e está certo. São recortes que se sobrepõem.
        assert placar(9, 19) + percentual_atrasados(13, 19) > 100

    def test_so_coincidem_quando_nao_ha_atraso_de_entrega(self):
        """Se todo atraso for de banca, aí sim viram complementares."""
        em_curso, atrasados_por_banca = 10, 4
        assert placar(em_curso - atrasados_por_banca, em_curso) == 60.0
        assert percentual_atrasados(atrasados_por_banca, em_curso) == 40.0


class TestArredondamento:
    @pytest.mark.parametrize(
        "atrasados,em_curso,esperado",
        [(1, 3, 33.3), (2, 3, 66.7), (1, 7, 14.3), (19, 19, 100.0), (0, 19, 0.0)],
    )
    def test_uma_casa_decimal(self, atrasados, em_curso, esperado):
        assert percentual_atrasados(atrasados, em_curso) == esperado
