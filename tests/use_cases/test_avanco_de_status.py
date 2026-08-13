"""🤖 §4: o status do projeto anda sozinho quando o fato já aconteceu.

Antes, cinco das seis transições do ciclo esperavam alguém trocar no seletor — e
ninguém trocava. Na base de teste, 5 de 29 projetos tinham banca REALIZADA e
continuavam em "Em andamento"; dois deles já tinham escopo entregue ao cliente.

⭐ **O teste que carrega o peso é `TestNaoBrigaComOManual`.** Automatizar o
avanço é fácil; o difícil é ele conviver com a pessoa. Sem a regra do
retrocesso, quem devolvesse um projeto de "Período de ajustes" para "Em
andamento" veria a correção sumir na madrugada seguinte, todas as noites.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.projeto import avancar_status
from src.use_cases.projeto.avancar_status import AvancarStatusAutomaticoUseCase


def escopo(id=1, entrega=None, status="em_andamento"):
    return SimpleNamespace(id=id, projeto_id=7, data_entrega_real=entrega, status=status)


def linha(anterior, novo, quando, por=None, id=1):
    return SimpleNamespace(
        status_anterior=anterior, status_novo=novo, alterado_em=quando, alterado_por=por, id=id
    )


@pytest.fixture
def avancar(monkeypatch):
    """`(executar, estado)` — `estado.gravado` mostra o status que ficou."""

    def _montar(*, status="em_andamento", escopos=(), bancas=None, historico=()):
        projeto = SimpleNamespace(id=7, nome="Projeto Alfa", status=status)
        estado = SimpleNamespace(gravado={}, historico=[])
        bancas = bancas or {}

        class ProjetoFake:
            def __init__(self, db): pass
            def get_all(self): return [projeto]
            def get_by_id(self, _id): return projeto
            def update(self, _id, **campos):
                estado.gravado.update(campos)
                for k, v in campos.items():
                    setattr(projeto, k, v)
                return projeto

        class EscopoFake:
            def __init__(self, db): pass
            def get_by_projeto(self, _id): return list(escopos)

        class BancaFake:
            def __init__(self, db): pass
            def get_by_projeto_escopo(self, escopo_id):
                return bancas.get(escopo_id)

        class HistoricoFake:
            def __init__(self, db): pass
            def get_by_projeto(self, _id): return list(historico)
            def create(self, **campos):
                estado.historico.append(campos)
                return SimpleNamespace(id=1, **campos)

        for nome, dublê in (
            ("ProjetoRepository", ProjetoFake),
            ("ProjetoEscopoRepository", EscopoFake),
            ("BancaRepository", BancaFake),
            ("ProjetoStatusHistoricoRepository", HistoricoFake),
        ):
            monkeypatch.setattr(avancar_status, nome, dublê)

        uc = AvancarStatusAutomaticoUseCase(db=None)
        return uc.execute, estado

    return _montar


def realizada():
    return SimpleNamespace(id=50, realizado_em=datetime(2026, 7, 9, 14, 0))


def nao_realizada():
    return SimpleNamespace(id=50, realizado_em=None)


class TestBancaLevaAValidacao:
    def test_avanca_quando_a_banca_aconteceu(self, avancar):
        executar, estado = avancar(
            status="em_andamento", escopos=[escopo(1)], bancas={1: realizada()}
        )

        assert executar() == [7]
        assert estado.gravado["status"] == "validacao_bancas"

    def test_banca_marcada_mas_nao_realizada_nao_avanca(self, avancar):
        """Marcar a data não é a banca acontecer."""
        executar, estado = avancar(
            status="em_andamento", escopos=[escopo(1)], bancas={1: nao_realizada()}
        )

        assert executar() == []
        assert estado.gravado == {}

    def test_uma_banca_de_varios_escopos_ja_basta(self, avancar):
        """A validação do projeto começou, mesmo com outro escopo por vir."""
        executar, _ = avancar(
            status="em_andamento",
            escopos=[escopo(1), escopo(2)],
            bancas={1: realizada(), 2: nao_realizada()},
        )

        assert executar() == [7]

    def test_registra_no_historico_sem_autor(self, avancar):
        """🤖 `alterado_por=None` é a convenção do sistema para "mudou sozinho" —
        a tela do Histórico lê o nulo e escreve "pelo sistema"."""
        executar, estado = avancar(
            status="em_andamento", escopos=[escopo(1)], bancas={1: realizada()}
        )
        executar()

        assert estado.historico[0]["alterado_por"] is None
        assert estado.historico[0]["status_anterior"] == "em_andamento"


class TestEntregaLevaAAjustes:
    def test_todos_entregues_avanca(self, avancar):
        executar, estado = avancar(
            status="validacao_bancas",
            escopos=[escopo(1, entrega="2026-07-20"), escopo(2, entrega="2026-07-22")],
        )

        assert executar() == [7]
        assert estado.gravado["status"] == "periodo_ajustes"

    def test_um_escopo_pendente_segura(self, avancar):
        executar, estado = avancar(
            status="validacao_bancas",
            escopos=[escopo(1, entrega="2026-07-20"), escopo(2)],
        )

        assert executar() == []
        assert estado.gravado == {}

    def test_escopo_cancelado_nao_conta(self, avancar):
        """⚠ Exigir entrega de algo cancelado travaria o avanço para sempre."""
        executar, estado = avancar(
            status="validacao_bancas",
            escopos=[escopo(1, entrega="2026-07-20"), escopo(2, status="cancelado")],
        )

        assert executar() == [7]

    def test_quem_passou_por_envio_tep_tambem_avanca(self, avancar):
        """`envio_tep` não tem gatilho (é documento fora da plataforma), mas
        quem passou por ele à mão volta ao fluxo automático."""
        executar, estado = avancar(
            status="envio_tep", escopos=[escopo(1, entrega="2026-07-20")]
        )

        assert executar() == [7]
        assert estado.gravado["status"] == "periodo_ajustes"


class TestNaoBrigaComOManual:
    """⭐ O automático cede à decisão da pessoa. Sem isto, o status se
    "consertaria" sozinho toda noite e a correção de quem entende do projeto
    duraria até a madrugada."""

    def test_retrocesso_manual_e_respeitado(self, avancar):
        """Alguém puxou o projeto de volta para Em andamento — o robô não
        desfaz, mesmo com a banca realizada pedindo o avanço."""
        executar, estado = avancar(
            status="em_andamento",
            escopos=[escopo(1)],
            bancas={1: realizada()},
            historico=[
                linha("em_andamento", "validacao_bancas", datetime(2026, 7, 1), por=None),
                linha("validacao_bancas", "em_andamento", datetime(2026, 7, 10), por=3),
            ],
        )

        assert executar() == []
        assert estado.gravado == {}

    def test_avanco_manual_nao_bloqueia_os_proximos(self, avancar):
        """Mover para FRENTE à mão não é retrocesso: o fluxo continua."""
        executar, estado = avancar(
            status="validacao_bancas",
            escopos=[escopo(1, entrega="2026-07-20")],
            historico=[linha("em_andamento", "validacao_bancas", datetime(2026, 7, 10), por=3)],
        )

        assert executar() == [7]

    def test_retrocesso_do_proprio_sistema_nao_conta(self, avancar):
        """Só decisão de PESSOA segura o automático. `alterado_por=None` é o
        próprio robô, e ele não se auto-bloqueia."""
        executar, _ = avancar(
            status="em_andamento",
            escopos=[escopo(1)],
            bancas={1: realizada()},
            historico=[linha("validacao_bancas", "em_andamento", datetime(2026, 7, 10), por=None)],
        )

        assert executar() == [7]

    def test_um_avanco_manual_posterior_devolve_ao_fluxo(self, avancar):
        """O que vale é o ÚLTIMO movimento: depois de um retrocesso, uma nova
        mudança manual para frente reabre o automático."""
        executar, _ = avancar(
            status="validacao_bancas",
            escopos=[escopo(1, entrega="2026-07-20")],
            historico=[
                linha("periodo_ajustes", "em_andamento", datetime(2026, 7, 5), por=3, id=1),
                linha("em_andamento", "validacao_bancas", datetime(2026, 7, 9), por=3, id=2),
            ],
        )

        assert executar() == [7]


class TestBordas:
    def test_projeto_pausado_nao_e_tocado(self, avancar):
        """⏸ Pausar é parar o relógio; virar o status desfaria a decisão."""
        executar, estado = avancar(
            status="pausado", escopos=[escopo(1)], bancas={1: realizada()}
        )

        assert executar() == []
        assert estado.gravado == {}

    def test_projeto_sem_escopo_nao_avanca(self, avancar):
        executar, _ = avancar(status="em_andamento", escopos=[])

        assert executar() == []

    def test_nunca_pula_etapa(self, avancar):
        """Um projeto em Vendido com banca realizada (dado inconsistente) não
        salta para Validação — o avanço é de uma casa, a partir da origem
        exata."""
        executar, estado = avancar(
            status="vendido", escopos=[escopo(1)], bancas={1: realizada()}
        )

        assert executar() == []
        assert estado.gravado == {}

    def test_finalizado_fica_onde_esta(self, avancar):
        """Encerrar é decisão da diretoria; nada aqui reabre nem re-encerra."""
        executar, estado = avancar(
            status="finalizado", escopos=[escopo(1, entrega="2026-07-20")]
        )

        assert executar() == []
        assert estado.gravado == {}
