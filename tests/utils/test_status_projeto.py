import pytest

from src.utils.exceptions import RegraDeNegocioError
from src.utils.status_projeto import (
    aplicar_transicao_manual,
    aplicar_volta,
    pausar,
    pode_pausar,
    retomar,
    status_anterior_manual,
    transicao_manual_valida,
    transicao_volta_valida,
)


class TestTransicaoManual:
    def test_em_andamento_avanca_para_validacao_bancas(self):
        assert aplicar_transicao_manual("em_andamento") == "validacao_bancas"

    def test_cadeia_completa_ate_finalizado(self):
        status = "ambientacao"
        sequencia = []
        while True:
            try:
                status = aplicar_transicao_manual(status)
                sequencia.append(status)
            except RegraDeNegocioError:
                break
        assert sequencia == [
            "em_andamento",
            "validacao_bancas",
            "envio_tep",
            "periodo_ajustes",
            "finalizado",
        ]

    def test_ambientacao_avanca_manualmente(self):
        """O §4 diz que esta transição é 🤖 automática ao fim dos dias de
        ambientação — mas o disparador não existe, e sem o caminho manual o
        projeto fica preso em Ambientação. Também é o caso legítimo de a
        equipe terminar antes do prazo."""
        assert aplicar_transicao_manual("ambientacao") == "em_andamento"

    def test_finalizado_nao_tem_proxima_transicao(self):
        with pytest.raises(RegraDeNegocioError):
            aplicar_transicao_manual("finalizado")

    def test_nao_pode_pular_etapa(self):
        assert not transicao_manual_valida("em_andamento", "finalizado")

    def test_vendido_nao_tem_transicao_manual_e_sim_automatica(self):
        with pytest.raises(RegraDeNegocioError):
            aplicar_transicao_manual("vendido")


class TestVoltarEtapa:
    """↩ Avançar sem poder voltar deixa um clique errado travando o projeto."""

    def test_volta_um_passo_na_fila(self):
        assert aplicar_volta("envio_tep") == "validacao_bancas"

    def test_a_volta_e_o_inverso_exato_da_ida(self):
        """Ida e volta têm que ser simétricas, ou o projeto fica preso num
        estado que só o banco desfaz."""
        for atual, proximo in [
            ("ambientacao", "em_andamento"),
            ("em_andamento", "validacao_bancas"),
            ("validacao_bancas", "envio_tep"),
            ("envio_tep", "periodo_ajustes"),
            ("periodo_ajustes", "finalizado"),
        ]:
            assert aplicar_transicao_manual(atual) == proximo
            assert aplicar_volta(proximo) == atual

    def test_projeto_finalizado_pode_ser_reaberto(self):
        """O caso em que o clique errado mais dói."""
        assert aplicar_volta("finalizado") == "periodo_ajustes"

    def test_volta_ate_ambientacao(self):
        """Em andamento chega por 🤖 automação, mas a volta manual passa por
        ela do mesmo jeito — senão não há como desfazer."""
        assert aplicar_volta("em_andamento") == "ambientacao"

    def test_ambientacao_e_o_piso_da_volta(self):
        """⛔ Não se volta para Vendido: isso seria desmarcar o kickoff, e a
        data já registrada é um fato do projeto, não um passo de fluxo."""
        assert status_anterior_manual("ambientacao") is None
        with pytest.raises(RegraDeNegocioError) as erro:
            aplicar_volta("ambientacao")
        assert "kickoff" in str(erro.value).lower()

    def test_nao_existe_transicao_de_ambientacao_para_vendido(self):
        assert not transicao_volta_valida("ambientacao", "vendido")

    def test_vendido_nao_volta(self):
        with pytest.raises(RegraDeNegocioError):
            aplicar_volta("vendido")

    def test_pausado_nao_volta_etapa_volta_pelo_retomar(self):
        with pytest.raises(RegraDeNegocioError) as erro:
            aplicar_volta("pausado")
        assert "retomar" in str(erro.value)

    def test_nao_pode_pular_etapa_para_tras(self):
        assert not transicao_volta_valida("finalizado", "em_andamento")

    def test_status_anterior_de_pausado_e_indefinido(self):
        assert status_anterior_manual("pausado") is None


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
