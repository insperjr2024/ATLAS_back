import pytest

from src.utils.exceptions import RegraDeNegocioError
from src.utils.status_projeto import (
    aplicar_transicao_manual,
    pausar,
    pode_pausar,
    retomar,
    transicao_manual_valida,
)


class TestTransicaoManual:
    def test_em_andamento_avanca_para_validacao_bancas(self):
        assert aplicar_transicao_manual("em_andamento") == "validacao_bancas"

    def test_cadeia_completa_ate_finalizado(self):
        status = "em_andamento"
        sequencia = []
        while True:
            try:
                status = aplicar_transicao_manual(status)
                sequencia.append(status)
            except RegraDeNegocioError:
                break
        assert sequencia == [
            "validacao_bancas",
            "envio_tep",
            "periodo_ajustes",
            "finalizado",
        ]

    def test_finalizado_nao_tem_proxima_transicao(self):
        with pytest.raises(RegraDeNegocioError):
            aplicar_transicao_manual("finalizado")

    def test_nao_pode_pular_etapa(self):
        assert not transicao_manual_valida("em_andamento", "finalizado")

    def test_vendido_nao_tem_transicao_manual_e_sim_automatica(self):
        with pytest.raises(RegraDeNegocioError):
            aplicar_transicao_manual("vendido")


class TestPausarERetomar:
    def test_projeto_em_andamento_pode_pausar(self):
        assert pode_pausar("em_andamento")

    def test_projeto_vendido_nao_pausa_ainda_nao_comecou(self):
        assert not pode_pausar("vendido")

    def test_projeto_finalizado_nao_pausa(self):
        assert not pode_pausar("finalizado")

    def test_pausar_devolve_status_pausado_e_guarda_o_anterior(self):
        novo, guardado = pausar("validacao_bancas")
        assert novo == "pausado"
        assert guardado == "validacao_bancas"

    def test_pausar_status_nao_pausavel_levanta_erro(self):
        with pytest.raises(RegraDeNegocioError):
            pausar("finalizado")

    def test_retomar_volta_ao_status_guardado(self):
        assert retomar("em_andamento") == "em_andamento"

    def test_retomar_sem_status_guardado_levanta_erro(self):
        with pytest.raises(RegraDeNegocioError):
            retomar(None)
