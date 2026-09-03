"""Quem entra no quadro de Execução (§7.2) — e quem não entra.

O bug: a aba iterava a lista crua de `_projetos_visiveis`, que só tira o
arquivado. Um projeto **finalizado** entrava com o selo "Quadro zerado" em
"Projetos sem tarefa atribuída", contava nos cinco KPIs do topo e ainda
aparecia na tabela de reunião semanal como quem não fez reunião.

O quadro dele está zerado porque ele ACABOU — é assim que um projeto termina.
E a MESMA tela já o excluía do "Atenção agora" da Visão geral e da fila de
cobrança dos Atrasos: o Monitoramento dizia duas coisas sobre o mesmo projeto.

Estes testes prendem a régua no lugar onde ela é uma só (`apenas_em_curso`),
para as três abas não voltarem a divergir.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.monitoramento.monitoramento import (
    ETAPAS_EM_CURSO,
    STATUS_FORA_DE_EXECUCAO,
    apenas_em_curso,
)
from src.utils.status_projeto import STATUS_VALIDOS


def projeto(id_, status):
    return SimpleNamespace(id=id_, nome=f"P{id_}", status=status)


class TestQuemSai:
    def test_finalizado_sai(self):
        """O caso relatado: projeto finalizado listado como "quadro zerado"."""
        assert apenas_em_curso([projeto(1, "finalizado")]) == []

    def test_pausado_sai(self):
        """⏸ Pausado é "parado" por decisão de gestão — não distribuir tarefa
        é exatamente o que se mandou acontecer."""
        assert apenas_em_curso([projeto(1, "pausado")]) == []

    def test_leva_junto_os_vizinhos_certos(self):
        """Só o finalizado sai da carteira; o resto continua sendo cobrado."""
        carteira = [
            projeto(1, "em_andamento"),
            projeto(2, "finalizado"),
            projeto(3, "periodo_ajustes"),
        ]
        assert [p.id for p in apenas_em_curso(carteira)] == [1, 3]


class TestQuemFica:
    @pytest.mark.parametrize("status", ETAPAS_EM_CURSO)
    def test_toda_etapa_do_ciclo_ativo_continua(self, status):
        """⚠ Inclui `periodo_ajustes` e `envio_tep`: estão no fim do funil,
        mas não acabaram — quem não distribui tarefa neles ainda é cobrança
        legítima. O corte é o status `finalizado`, não "está perto do fim"."""
        assert len(apenas_em_curso([projeto(1, status)])) == 1

    def test_carteira_vazia_nao_quebra(self):
        assert apenas_em_curso([]) == []


class TestReguaUnica:
    def test_a_particao_e_exata(self):
        """Todo status válido está de um lado OU do outro — nenhum se perde,
        nenhum entra nos dois. É o que garante que a soma da tela feche."""
        carteira = [projeto(i, s) for i, s in enumerate(STATUS_VALIDOS)]
        ficam = {p.status for p in apenas_em_curso(carteira)}
        assert ficam | set(STATUS_FORA_DE_EXECUCAO) == set(STATUS_VALIDOS)
        assert ficam & set(STATUS_FORA_DE_EXECUCAO) == set()

    def test_nenhuma_etapa_em_curso_esta_na_lista_de_exclusao(self):
        """As duas constantes se contradiriam em silêncio: a pizza da Visão
        geral desenharia uma fatia para uma etapa que a Execução ignora."""
        assert set(ETAPAS_EM_CURSO) & set(STATUS_FORA_DE_EXECUCAO) == set()
