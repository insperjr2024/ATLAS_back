"""O status geral pelas cores dos pilares (Health Track §4 e §5).

**O ponto do desenho: amarelo é o resto.** Vermelho e verde têm limites; o
que não é nenhum dos dois é amarelo. Assim nenhuma combinação fica sem
status, nem com a regra inicial nem com a que a diretoria vier a configurar.
"""

from datetime import datetime
from itertools import product
from types import SimpleNamespace

import pytest

from src.utils.health_track_status import (
    RegraStatusGeral,
    ReguasStatus,
    calcular_status_geral,
    faixa_amarela,
    status_geral,
    status_geral_ou_nada,
)

#: A regra que a migration semeia — repetida aqui de propósito: o código de
#: produção não tem mais nenhuma cópia dela.
INICIAL = RegraStatusGeral(verde_max_amarelos=1, verde_max_vermelhos=0, vermelho_min_amarelos=3, vermelho_min_vermelhos=1)
SO_ZERO_AMARELOS = RegraStatusGeral(verde_max_amarelos=0, verde_max_vermelhos=0, vermelho_min_amarelos=3, vermelho_min_vermelhos=1)


def versao(regra: RegraStatusGeral, desde: datetime):
    return SimpleNamespace(vigente_desde=desde, **regra.__dict__)


#: Inicial desde sempre; a diretoria apertou o verde em 1º de novembro.
REGUAS = ReguasStatus([versao(SO_ZERO_AMARELOS, datetime(2026, 11, 1)), versao(INICIAL, datetime(2000, 1, 1))])
SO_INICIAL = ReguasStatus([versao(INICIAL, datetime(2000, 1, 1))])


def cores(verdes=0, amarelos=0, vermelhos=0):
    return ["verde"] * verdes + ["amarelo"] * amarelos + ["vermelho"] * vermelhos


class TestRegraInicialDaSpec:
    @pytest.mark.parametrize(
        "combinacao,esperado",
        [
            (cores(verdes=6), "verde"),                       # 0 amarelos e 0 vermelhos
            (cores(verdes=5, amarelos=1), "verde"),           # até 1 amarelo
            (cores(verdes=4, amarelos=2), "amarelo"),         # 2 amarelos, nenhum vermelho
            (cores(verdes=3, amarelos=3), "vermelho"),        # 3 ou mais amarelos
            (cores(amarelos=6), "vermelho"),
            (cores(verdes=5, vermelhos=1), "vermelho"),       # a lacuna do §4, fechada pelo §5
            (cores(verdes=4, amarelos=1, vermelhos=1), "vermelho"),
            (cores(vermelhos=6), "vermelho"),
        ],
    )
    def test_cada_combinacao_da_spec(self, combinacao, esperado):
        assert calcular_status_geral(combinacao, INICIAL) == esperado

    def test_a_ordem_das_cores_nao_importa(self):
        assert calcular_status_geral(["amarelo", "verde", "amarelo"], INICIAL) == "amarelo"


class TestSemBuracos:
    @pytest.mark.parametrize(
        "regra",
        [
            INICIAL,
            SO_ZERO_AMARELOS,                                  # "Apenas 0 amarelos -> verde" (§5)
            # "Até 2 amarelos -> verde" (§5) — amarelo fica sem combinação nenhuma, e tudo bem.
            RegraStatusGeral(verde_max_amarelos=2, verde_max_vermelhos=0, vermelho_min_amarelos=3, vermelho_min_vermelhos=1),
            # Limites que se cruzam: vermelho vence, porque é checado primeiro.
            RegraStatusGeral(verde_max_amarelos=5, verde_max_vermelhos=2, vermelho_min_amarelos=1, vermelho_min_vermelhos=1),
        ],
    )
    def test_toda_combinacao_de_6_pilares_tem_status(self, regra):
        for combinacao in product(["verde", "amarelo", "vermelho"], repeat=6):
            assert calcular_status_geral(combinacao, regra) in ("verde", "amarelo", "vermelho")

    def test_limites_cruzados_resolvem_para_o_mais_grave(self):
        cruzada = RegraStatusGeral(verde_max_amarelos=5, verde_max_vermelhos=0, vermelho_min_amarelos=1, vermelho_min_vermelhos=1)
        assert calcular_status_geral(cores(verdes=5, amarelos=1), cruzada) == "vermelho"


class TestVersoes:
    def test_cada_momento_pega_a_versao_que_ja_valia(self):
        assert REGUAS.vigente_em(datetime(2026, 10, 31, 23, 59)) == INICIAL
        assert REGUAS.vigente_em(datetime(2026, 11, 1)) == SO_ZERO_AMARELOS  # vale a partir do instante
        assert REGUAS.vigente_em(datetime(2027, 1, 1)) == SO_ZERO_AMARELOS

    def test_atual_e_a_mais_recente_independente_da_ordem_recebida(self):
        assert REGUAS.atual() == SO_ZERO_AMARELOS

    def test_antes_da_primeira_versao_nao_ha_regra(self):
        assert REGUAS.vigente_em(datetime(1999, 1, 1)) is None

    def test_sem_versao_nenhuma_nao_ha_status(self):
        assert status_geral(cores(verdes=6), datetime(2026, 10, 1), ReguasStatus([])) is None


class TestDuasReguas:
    def test_sem_mudanca_de_regra_os_dois_coincidem(self):
        assert status_geral(cores(verdes=5, amarelos=1), datetime(2026, 10, 1), SO_INICIAL) == {
            "na_epoca": "verde",
            "pela_regra_atual": "verde",
        }

    def test_ciclo_de_antes_da_mudanca(self):
        """Em outubro valia "até 1 amarelo -> verde"; em novembro a diretoria
        apertou para "0 amarelos". O ciclo de outubro com 1 amarelo continua
        verde na época, e seria amarelo hoje."""
        assert status_geral(cores(verdes=5, amarelos=1), datetime(2026, 10, 1), REGUAS) == {
            "na_epoca": "verde",
            "pela_regra_atual": "amarelo",
        }

    def test_ciclo_de_depois_da_mudanca(self):
        assert status_geral(cores(verdes=5, amarelos=1), datetime(2026, 11, 15), REGUAS) == {
            "na_epoca": "amarelo",
            "pela_regra_atual": "amarelo",
        }


class TestSoComTodosOsPilares:
    def test_pilar_sem_cor_deixa_status_nulo(self):
        """3 verdes e 3 em branco não é um projeto verde."""
        assert status_geral_ou_nada(["verde", "verde", "verde", None, None, None], datetime(2026, 10, 1), SO_INICIAL) is None

    def test_sem_avaliacao_nenhuma_e_nulo(self):
        assert status_geral_ou_nada([], None, SO_INICIAL) is None

    def test_completo_calcula(self):
        assert status_geral_ou_nada(cores(verdes=6), datetime(2026, 10, 1), SO_INICIAL)["na_epoca"] == "verde"


class TestFaixaAmarela:
    def test_regra_inicial_e_o_exemplo_do_paragrafo_5(self):
        """"Mínimo de amarelos: 2, Máximo de amarelos: 2, Máximo de vermelhos: 0"."""
        assert faixa_amarela(INICIAL) == {"min_amarelos": 2, "max_amarelos": 2, "max_vermelhos": 0}

    def test_faixa_bate_com_o_calculo_em_toda_combinacao(self):
        """O que a tela diz sobre o amarelo é o que o cálculo faz."""
        for regra in (INICIAL, SO_ZERO_AMARELOS):
            faixa = faixa_amarela(regra)
            for a, v in product(range(7), range(7)):
                if a + v > 6:
                    continue
                na_faixa = faixa["min_amarelos"] <= a <= faixa["max_amarelos"] and v <= faixa["max_vermelhos"]
                assert (calcular_status_geral(cores(6 - a - v, a, v), regra) == "amarelo") == na_faixa

    def test_folga_entre_vermelhos_deixa_amarelo_sem_minimo_de_amarelos(self):
        """Verde aceita 0 vermelhos e vermelho começa em 2: com 1 vermelho e
        nenhum amarelo, o projeto já é amarelo."""
        folga = RegraStatusGeral(verde_max_amarelos=1, verde_max_vermelhos=0, vermelho_min_amarelos=3, vermelho_min_vermelhos=2)

        assert faixa_amarela(folga)["min_amarelos"] == 0
        assert calcular_status_geral(cores(verdes=5, vermelhos=1), folga) == "amarelo"
