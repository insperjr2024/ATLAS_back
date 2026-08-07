"""§13: marcar a entrega é livre; MUDAR uma entrega já registrada é da diretoria.

A assimetria é o ponto inteiro. Registrar a entrega é o passo em que o
coordenador fecha o escopo no cronograma — travá-lo faria o time depender da
diretoria para anotar o que já aconteceu. Mudar a data depois é outra coisa: a
data que o cliente ouviu vira outra, e sem gate um escopo entregue com atraso
podia ter a data empurrada em silêncio até o atraso sumir do monitoramento.

⭐ **Existe UMA entrega, não duas.** "Entrega ao cliente" e "entrega do escopo"
são a mesma coisa: o cliente recebe quando o escopo é entregue. A do projeto é
derivada da última — não há data própria para ela.

⚠ E, diferente da banca, a entrega **não** precisa caber na janela do escopo: a
janela é o tempo de TRABALHO vendido, e a apresentação ao cliente costuma
acontecer dias depois da banca.

Dublês à mão, classes de repositório trocadas no módulo via `monkeypatch` —
mesmo idioma de `test_banca_na_janela.py`.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from src.use_cases.projeto_escopo import update_escopo_projeto
from src.use_cases.projeto_escopo.update_escopo_projeto import (
    RegistrarEntregaEscopoRequest,
    RegistrarEntregaEscopoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

QUI_03_09 = date(2026, 9, 3)
QUI_15_10 = date(2026, 10, 15)
QUI_22_10 = date(2026, 10, 22)

ANA = SimpleNamespace(id=10, nome="Ana Souza", posicao="coordenador")
DANI = SimpleNamespace(id=1, nome="Dani Alves", posicao="diretor")


@pytest.fixture
def entregar_escopo(monkeypatch):
    """`(executar, estado)` — `estado.alteracoes` mostra o que foi registrado."""

    def _montar(entrega_atual=None, *, banca_realizada=True):
        estado = SimpleNamespace(alteracoes=[], gravado={})
        escopo = SimpleNamespace(
            id=7,
            projeto_id=3,
            escopo_id=None,
            nome_customizado="Elaboração Contratual",
            data_inicio=QUI_03_09,
            data_entrega_real=entrega_atual,
        )

        class EscopoProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return escopo
            def update(self, _id, **campos):
                estado.gravado.update(campos)
                for k, v in campos.items():
                    setattr(escopo, k, v)
                return escopo

        class BancaFake:
            def __init__(self, db): pass
            def get_by_projeto_escopo(self, _id):
                if not banca_realizada:
                    return None
                return SimpleNamespace(id=50, realizado_em=QUI_15_10)

        class ProjetoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return None  # sem projeto, não notifica

        class CatalogoFake:
            def __init__(self, db): pass
            def get_by_id(self, _id): return None

        class AlteracaoFake:
            def __init__(self, db): pass
            def create(self, **campos):
                estado.alteracoes.append(campos)
                return SimpleNamespace(id=1, **campos)

        for nome, fake in [
            ("ProjetoEscopoRepository", EscopoProjetoFake),
            ("BancaRepository", BancaFake),
            ("ProjetoRepository", ProjetoFake),
            ("EscopoRepository", CatalogoFake),
            ("EntregaAlteracaoRepository", AlteracaoFake),
        ]:
            monkeypatch.setattr(update_escopo_projeto, nome, fake)

        uc = RegistrarEntregaEscopoUseCase(db=None)

        def executar(data=QUI_15_10, quem=ANA, justificativa=None):
            return uc.execute(
                escopo.id,
                RegistrarEntregaEscopoRequest(
                    data_entrega_real=data, justificativa=justificativa
                ),
                eh_diretor=quem.posicao == "diretor",
                current_user=quem,
            )

        return executar, estado

    return _montar


class TestEntregaDoEscopo:
    def test_a_primeira_marcacao_e_livre(self, entregar_escopo):
        """O passo normal do fluxo: o coordenador fecha o escopo sozinho."""
        executar, estado = entregar_escopo()

        resposta = executar()

        assert resposta["data_entrega_real"] == QUI_15_10
        assert estado.gravado["status"] == "entregue"

    def test_a_primeira_marcacao_entra_no_historico(self, entregar_escopo):
        """Com `data_anterior` nula — é o "de onde veio" da promessa."""
        executar, estado = entregar_escopo()

        executar()

        (registro,) = estado.alteracoes
        assert registro["data_anterior"] is None
        assert registro["data_nova"] == QUI_15_10
        # Ninguém autorizou porque ninguém precisou.
        assert registro["autorizado_por"] is None

    def test_mudar_uma_entrega_registrada_barra_o_coordenador(self, entregar_escopo):
        """A mensagem diz a data que já valia — senão a pessoa não sabe o que
        está tentando sobrescrever."""
        executar, _ = entregar_escopo(entrega_atual=QUI_15_10)

        with pytest.raises(RegraDeNegocioError, match="diretoria"):
            executar(data=QUI_22_10)

    def test_a_diretoria_muda_com_justificativa(self, entregar_escopo):
        executar, estado = entregar_escopo(entrega_atual=QUI_15_10)

        executar(data=QUI_22_10, quem=DANI, justificativa="Agenda do cliente")

        (registro,) = estado.alteracoes
        assert registro["data_anterior"] == QUI_15_10
        assert registro["data_nova"] == QUI_22_10
        assert registro["autorizado_por"] == DANI.id

    def test_a_diretoria_tambem_precisa_justificar(self, entregar_escopo):
        executar, _ = entregar_escopo(entrega_atual=QUI_15_10)

        with pytest.raises(RegraDeNegocioError, match="justificativa"):
            executar(data=QUI_22_10, quem=DANI)

    def test_salvar_a_mesma_data_nao_e_alteracao(self, entregar_escopo):
        """Reenviar o mesmo dia não pode pedir diretoria nem virar linha no
        Histórico."""
        executar, estado = entregar_escopo(entrega_atual=QUI_15_10)

        executar(data=QUI_15_10)

        assert estado.alteracoes == []

    def test_a_trava_do_5_5_continua_de_pe(self, entregar_escopo):
        """O gate novo não substitui o antigo: sem banca realizada, nada vai ao
        cliente."""
        executar, _ = entregar_escopo(banca_realizada=False)

        with pytest.raises(RegraDeNegocioError, match="banca"):
            executar()


class TestEntregaForaDaJanela:
    """A entrega pode cair DEPOIS do fim da janela do escopo — a banca não.

    O exemplo que a diretoria deu: escopo com janela até o dia 20, banca no dia
    20, entrega no dia 23. A janela mede o trabalho vendido; a apresentação ao
    cliente vem depois dela, e barrar isso obrigaria a mentir a data ou a
    "gastar" janela com uma reunião que não é trabalho.
    """

    def test_entrega_depois_do_fim_da_janela_passa(self, entregar_escopo):
        executar, estado = entregar_escopo()

        # A janela do dublê termina bem antes; nenhuma validação de janela
        # deve existir neste caminho.
        resposta = executar(data=date(2026, 12, 23))

        assert resposta["data_entrega_real"] == date(2026, 12, 23)
        assert estado.gravado["status"] == "entregue"
