"""A distribuição do portfólio pelas etapas (§7.1), que alimenta a pizza.

⭐ **A propriedade que importa é a soma.** A pizza mostra o total de projetos
ativos no meio e uma fatia por etapa. Se a soma das fatias não bater com o
número do centro, o gráfico mente — e mente do jeito difícil de pegar, porque
cada número isolado parece certo.

`_por_etapa` recebe a mesma lista `em_curso` de onde sai `total_ativos`, então
a igualdade é estrutural. Estes testes prendem isso: se alguém trocar a base de
uma das duas pontas, quebra aqui e não na tela da diretoria.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.monitoramento.monitoramento import (
    ETAPAS_EM_CURSO,
    VisaoGeralUseCase,
)


def projeto(id_, nome, status):
    return SimpleNamespace(id=id_, nome=nome, status=status)


def por_etapa(em_curso):
    uc = VisaoGeralUseCase.__new__(VisaoGeralUseCase)
    return uc._por_etapa(em_curso)


#: Um portfólio com etapa repetida, etapa vazia e nomes fora de ordem.
CARTEIRA = [
    projeto(1, "Zeta", "em_andamento"),
    projeto(2, "Alfa", "em_andamento"),
    projeto(3, "Beta", "vendido"),
    projeto(4, "Gama", "validacao_bancas"),
]


class TestSomaDasFatias:
    def test_a_soma_bate_com_o_total_de_ativos(self):
        """O número do meio da pizza é `len(em_curso)`. Esta é a igualdade que
        o gráfico inteiro promete."""
        assert sum(e["total"] for e in por_etapa(CARTEIRA)) == len(CARTEIRA)

    @pytest.mark.parametrize("quantidade", [0, 1, 7, 30])
    def test_a_soma_bate_para_qualquer_carteira(self, quantidade):
        carteira = [
            projeto(i, f"P{i}", ETAPAS_EM_CURSO[i % len(ETAPAS_EM_CURSO)])
            for i in range(quantidade)
        ]
        assert sum(e["total"] for e in por_etapa(carteira)) == quantidade

    def test_nenhum_projeto_se_perde_no_caminho(self):
        """Complemento da soma: os ids que entram são exatamente os que saem."""
        saida = {p["id"] for e in por_etapa(CARTEIRA) for p in e["projetos"]}
        assert saida == {p.id for p in CARTEIRA}


class TestOrdemDasEtapas:
    """A ordem é o dado. Status é uma sequência, e a pizza se lê como funil —
    ordenar por quantidade embaralharia as etapas."""

    def test_segue_o_ciclo_de_vida_e_nao_a_quantidade(self):
        etapas = [e["status"] for e in por_etapa(CARTEIRA)]
        assert etapas == list(ETAPAS_EM_CURSO)

    def test_vendido_vem_antes_de_em_andamento_mesmo_tendo_menos(self):
        etapas = [e["status"] for e in por_etapa(CARTEIRA)]
        assert etapas.index("vendido") < etapas.index("em_andamento")


class TestEtapaVazia:
    def test_entra_com_zero_em_vez_de_sumir(self):
        """Sumir da legenda faria parecer que a etapa não existe, quando o que
        se quer saber é justamente que ela está vazia."""
        resultado = {e["status"]: e for e in por_etapa(CARTEIRA)}
        assert resultado["envio_tep"]["total"] == 0
        assert resultado["envio_tep"]["projetos"] == []

    def test_carteira_vazia_ainda_devolve_todas_as_etapas(self):
        assert len(por_etapa([])) == len(ETAPAS_EM_CURSO)


class TestForaDoCiclo:
    """`finalizado` e `pausado` nunca chegam aqui — `em_curso` já os removeu.
    Se chegarem, não podem virar fatia, senão a soma estoura o centro."""

    def test_status_fora_do_ciclo_nao_vira_fatia(self):
        carteira = CARTEIRA + [projeto(9, "Velho", "finalizado")]
        etapas = [e["status"] for e in por_etapa(carteira)]
        assert "finalizado" not in etapas


class TestProjetosDaFatia:
    """A fatia é clicável: só a contagem não responde "quais são esses?"."""

    def test_traz_id_e_nome(self):
        resultado = {e["status"]: e for e in por_etapa(CARTEIRA)}
        assert resultado["vendido"]["projetos"] == [{"id": 3, "nome": "Beta"}]

    def test_ordenados_por_nome(self):
        """A ordem do banco não é estável; sem isto a lista embaralha a cada
        refresh."""
        resultado = {e["status"]: e for e in por_etapa(CARTEIRA)}
        nomes = [p["nome"] for p in resultado["em_andamento"]["projetos"]]
        assert nomes == ["Alfa", "Zeta"]
