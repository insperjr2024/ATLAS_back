"""O ciclo de vida do §4, depois que ele virou livre entre as etapas.

A régua antiga era uma fila (avança um passo, volta um passo). Hoje as etapas
ativas transitam livremente entre si, nos dois sentidos, e sobrou uma única
regra de ordem: sair de **Vendido** só dá pra Ambientação, e só com o kickoff
marcado. Pausado continua à parte — entra pelo `pausar`, sai pelo `retomar`.
"""

import pytest

from src.utils.exceptions import RegraDeNegocioError
from src.utils.status_projeto import (
    STATUS_ATIVOS,
    STATUS_ORDEM,
    destinos_validos,
    pausar,
    pode_pausar,
    retomar,
    transicao_manual_valida,
)

# A fila do §4, que hoje é só a ordem de exibição — não mais a ordem obrigatória.
FILA = [
    ("ambientacao", "em_andamento"),
    ("em_andamento", "validacao_bancas"),
    ("validacao_bancas", "envio_tep"),
    ("envio_tep", "periodo_ajustes"),
    ("periodo_ajustes", "finalizado"),
]


class TestTransicaoManual:
    def test_em_andamento_avanca_para_validacao_bancas(self):
        assert transicao_manual_valida("em_andamento", "validacao_bancas", tem_kickoff=True)

    def test_cadeia_completa_ate_finalizado(self):
        """Passo a passo pela fila continua sendo um caminho válido — o que
        mudou é que ele deixou de ser o único."""
        status = "ambientacao"
        sequencia = []
        for _, proximo in FILA:
            assert transicao_manual_valida(status, proximo, tem_kickoff=True)
            status = proximo
            sequencia.append(status)
        assert sequencia == [
            "em_andamento",
            "validacao_bancas",
            "envio_tep",
            "periodo_ajustes",
            "finalizado",
        ]

    def test_ambientacao_avanca_manualmente(self):
        """O §4 diz que esta transição é 🤖 automática ao fim dos dias de
        ambientação (`encerrar_ambientacao`) — mas o caminho manual segue
        aberto, para a equipe que termina antes do prazo."""
        assert transicao_manual_valida("ambientacao", "em_andamento", tem_kickoff=True)

    def test_finalizado_nao_e_o_fim_da_linha(self):
        """↩ Reabrir um projeto finalizado é o caso em que o clique errado
        mais dói — e hoje ele é uma transição comum, não uma exceção."""
        assert transicao_manual_valida("finalizado", "periodo_ajustes", tem_kickoff=True)
        assert transicao_manual_valida("finalizado", "em_andamento", tem_kickoff=True)

    def test_pode_pular_etapa(self):
        """A régua antiga proibia; a nova deixa a coordenação escolher
        qualquer etapa ativa da lista."""
        assert transicao_manual_valida("em_andamento", "finalizado", tem_kickoff=True)

    def test_toda_etapa_ativa_alcanca_todas_as_outras(self):
        for atual in STATUS_ATIVOS:
            for novo in STATUS_ATIVOS:
                if atual != novo:
                    assert transicao_manual_valida(atual, novo, tem_kickoff=True)

    def test_a_ida_e_a_volta_sao_ambas_validas(self):
        """Ida e volta simétricas, ou o projeto fica preso num estado que só o
        banco desfaz."""
        for atual, proximo in FILA:
            assert transicao_manual_valida(atual, proximo, tem_kickoff=True)
            assert transicao_manual_valida(proximo, atual, tem_kickoff=True)

    def test_ficar_no_mesmo_status_nao_e_transicao(self):
        assert not transicao_manual_valida("em_andamento", "em_andamento", tem_kickoff=True)

    def test_nao_se_volta_para_vendido(self):
        """⛔ Voltar pra Vendido seria desmarcar o kickoff, e a data já
        registrada é um fato do projeto, não um passo de fluxo."""
        for ativo in STATUS_ATIVOS:
            assert not transicao_manual_valida(ativo, "vendido", tem_kickoff=True)

    def test_pausado_nao_sai_pelo_seletor_de_etapa(self):
        """De Pausado só se sai pelo retomar, que sabe o status guardado."""
        assert not transicao_manual_valida("pausado", "em_andamento", tem_kickoff=True)
        assert destinos_validos("pausado", tem_kickoff=True) == []

    def test_nao_se_pausa_pelo_seletor_de_etapa(self):
        assert "pausado" not in destinos_validos("em_andamento", tem_kickoff=True)
        assert not transicao_manual_valida("em_andamento", "pausado", tem_kickoff=True)


class TestKickoffComoPreRequisito:
    """🗓 O kickoff *habilita* a saída de Vendido; quem aciona é uma pessoa."""

    def test_vendido_vira_ambientacao_com_kickoff_marcado(self):
        assert transicao_manual_valida("vendido", "ambientacao", tem_kickoff=True)

    def test_vendido_nao_sai_sem_kickoff(self):
        assert not transicao_manual_valida("vendido", "ambientacao", tem_kickoff=False)

    def test_vendido_so_vai_para_ambientacao(self):
        """Mesmo com kickoff, Vendido não pula direto pro meio do projeto."""
        for destino in STATUS_ORDEM[2:]:
            assert not transicao_manual_valida("vendido", destino, tem_kickoff=True)

    def test_destinos_de_vendido_dependem_do_kickoff(self):
        assert destinos_validos("vendido", tem_kickoff=True) == ["ambientacao"]
        assert destinos_validos("vendido", tem_kickoff=False) == []

    def test_kickoff_nao_restringe_quem_ja_saiu_de_vendido(self):
        """Uma vez em Ambientação, a data já foi registrada — a régua do
        kickoff não volta a valer."""
        assert transicao_manual_valida("em_andamento", "envio_tep", tem_kickoff=False)


class TestDestinosValidos:
    """O seletor de etapa e o validador do clique têm que dizer a mesma coisa."""

    def test_lista_todas_as_ativas_menos_a_atual(self):
        assert destinos_validos("em_andamento", tem_kickoff=True) == [
            "ambientacao",
            "validacao_bancas",
            "envio_tep",
            "periodo_ajustes",
            "finalizado",
        ]

    def test_finalizado_ainda_tem_para_onde_ir(self):
        assert destinos_validos("finalizado", tem_kickoff=True) == [
            "ambientacao",
            "em_andamento",
            "validacao_bancas",
            "envio_tep",
            "periodo_ajustes",
        ]

    def test_destinos_batem_com_a_validacao_do_clique(self):
        for atual in STATUS_ORDEM + ["pausado"]:
            for tem_kickoff in (True, False):
                destinos = destinos_validos(atual, tem_kickoff)
                for candidato in STATUS_ORDEM + ["pausado"]:
                    assert transicao_manual_valida(atual, candidato, tem_kickoff) == (
                        candidato in destinos
                    )


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

    def test_pausar_projeto_ja_pausado_levanta_erro(self):
        with pytest.raises(RegraDeNegocioError):
            pausar("pausado")

    def test_retomar_volta_ao_status_guardado(self):
        assert retomar("em_andamento") == "em_andamento"

    def test_pausar_e_retomar_devolvem_o_projeto_onde_estava(self):
        for etapa in ["ambientacao", "em_andamento", "validacao_bancas", "envio_tep", "periodo_ajustes"]:
            _, guardado = pausar(etapa)
            assert retomar(guardado) == etapa

    def test_retomar_sem_status_guardado_levanta_erro(self):
        with pytest.raises(RegraDeNegocioError):
            retomar(None)
