"""⭐ O ajuste manual da janela — a porta da diretoria de projetos.

A janela do escopo é parede para todo o resto da tela: pintar ou arrastar uma
etapa para fora dela é recusado, e o caminho é pedir dias de ajuste, que tem
prazo (§8). Passado o prazo, ninguém mais mexia — nem quem decide sobre prazo.

Estes testes cobrem a saída, e o que eles protegem é a linha entre as duas
coisas que "sem restrição alguma" NÃO quis dizer:

- **Regra de negócio sai**: janela, prazo, estado do projeto, banca. Nada
  disso é consultado aqui.
- **Integridade do dado fica**: janela de zero dia. Sem ela, a contagem de
  dias úteis e o desenho do calendário passam a mentir.

⭐ E a decisão central: `dias_uteis_vendidos` NUNCA é tocado. Ele é o registro
comercial (ver `ProjetoEscopoModel`), e a janela cresce ou encolhe por
`dias_uteis_ajustados` — que por isso passa a poder ser negativo.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.cronograma import ajuste_manual
from src.use_cases.cronograma.ajuste_manual import (
    AjusteManualRequest,
    AjusteManualUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


def escopo(vendidos=25, ajustados=0):
    return SimpleNamespace(
        id=7,
        projeto_id=3,
        dias_uteis_vendidos=vendidos,
        dias_uteis_ajustados=ajustados,
    )


@pytest.fixture
def ajustar(monkeypatch):
    """`(executar, estado)` com o repositório trocado por um dublê."""

    def _montar(alvo=None):
        alvo = alvo if alvo is not None else escopo()
        estado = SimpleNamespace(escopo=[])

        class EscopoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return alvo if _id == alvo.id else None
            def update(self, _id, **campos):
                estado.escopo.append(campos)
                return SimpleNamespace(id=_id, **campos)

        monkeypatch.setattr(ajuste_manual, "ProjetoEscopoRepository", EscopoFake)

        def executar(dias):
            return AjusteManualUseCase(db=None).execute(
                alvo.id, AjusteManualRequest(dias_uteis_janela=dias)
            )

        return executar, estado

    return _montar


class TestAJanela:
    def test_esticar_soma_nos_ajustados_e_nao_no_vendido(self, ajustar):
        """⭐ 25 vendidos + janela de 40 = 15 ajustados. O vendido fica."""
        executar, estado = ajustar()

        resposta = executar(40)

        assert estado.escopo == [{"dias_uteis_ajustados": 15}]
        assert resposta["dias_uteis_vendidos"] == 25

    def test_encolher_abaixo_do_vendido_deixa_ajustados_negativo(self, ajustar):
        """A alternativa seria sobrescrever o vendido — e aí "vendemos 25 e
        entregamos em 10" viraria "vendemos 10", que é o que o registro
        comercial existe para não deixar acontecer."""
        executar, estado = ajustar()

        executar(10)

        assert estado.escopo == [{"dias_uteis_ajustados": -15}]

    def test_a_janela_ja_ajustada_e_recalculada_do_total_e_nao_somada(self, ajustar):
        """Quem chega com 25+5 e pede 40 fica com 15 ajustados, não 20: o
        campo é o TOTAL da janela, não um incremento."""
        executar, estado = ajustar(escopo(ajustados=5))

        executar(40)

        assert estado.escopo == [{"dias_uteis_ajustados": 15}]

    def test_a_janela_igual_ao_vendido_zera_o_ajuste(self, ajustar):
        """Desfazer um ajuste anterior é pedir de volta o número vendido."""
        executar, estado = ajustar(escopo(ajustados=10))

        executar(25)

        assert estado.escopo == [{"dias_uteis_ajustados": 0}]

    def test_janela_de_um_dia_passa(self, ajustar):
        """O piso é 1, e ele vale: encolher ao extremo é permitido."""
        executar, estado = ajustar()

        executar(1)

        assert estado.escopo == [{"dias_uteis_ajustados": -24}]


class TestIntegridade:
    """O que "sem restrição alguma" não cobre: dado que se contradiz."""

    def test_janela_de_zero_dia_nao_passa(self, ajustar):
        executar, estado = ajustar()

        with pytest.raises(RegraDeNegocioError, match="pelo menos 1 dia útil"):
            executar(0)

        assert estado.escopo == []

    def test_janela_negativa_nao_passa(self, ajustar):
        executar, estado = ajustar()

        with pytest.raises(RegraDeNegocioError, match="pelo menos 1 dia útil"):
            executar(-5)

        assert estado.escopo == []

    def test_escopo_inexistente_nao_passa(self, ajustar):
        ajustar()

        with pytest.raises(RegraDeNegocioError, match="Escopo não encontrado"):
            AjusteManualUseCase(db=None).execute(
                999, AjusteManualRequest(dias_uteis_janela=40)
            )
